"""GUI-independent, synchronous capture lifecycle; no browser or USB adapter."""

from dataclasses import dataclass, replace
from threading import Event, Lock, Thread
from time import monotonic
from typing import Callable, Protocol

from .frames import RGBFrame
from .settings import Settings, SettingsError, SettingsStore, _checked, _ACK_ERROR
from .devices import enumerate_devices
from .transport import Transport


class LifecycleError(RuntimeError):
    """Actionable lifecycle rejection, without private input or backend errors."""


@dataclass(frozen=True)
class SourceSample:
    """An observation, not server health. Only ready samples may carry frames."""

    state: str
    frame: RGBFrame | None = None
    live_connected: bool | None = None
    data_stale: bool | None = None

    def __post_init__(self):
        if self.state not in {"loading", "ready", "empty", "error"}:
            raise ValueError("Source state must be loading, ready, empty or error.")
        if self.frame is not None:
            if self.state != "ready":
                raise ValueError("Only ready source samples may contain a frame.")
            if not isinstance(self.frame, RGBFrame):
                raise TypeError("Source frame must be an RGBFrame or None.")
        if any(value is not None and type(value) is not bool
               for value in (self.live_connected, self.data_stale)):
            raise TypeError("Source metadata must be boolean or None.")


class SourceSession(Protocol):
    """All calls, including factory construction, belong to one worker.

    close() must handle partially failed open(). Factories that raise before
    returning must themselves clean up anything they allocated. read() returns
    observations; raise for recoverable setup/capture failures. Calls must have
    bounded backend timeouts: Stop cannot interrupt a synchronous backend call.
    """

    def open(self) -> None: ...
    def read(self) -> SourceSample: ...
    def close(self) -> None: ...


@dataclass(frozen=True)
class StartContext:
    """One Start's frozen settings and its exact cooperative cancellation event."""

    settings: Settings
    cancel: Event


@dataclass(frozen=True)
class Snapshot:
    state: str = "stopped"
    source_state: str = "stopped"
    output_state: str = "simulated-closed"
    live_connected: bool | None = None
    data_stale: bool | None = None
    latest_frame: RGBFrame | None = None
    frames_sent: int = 0
    failures: int = 0
    retries: int = 0
    error: str | None = None
    worker_alive: bool = False
    exit_requested: bool = False
    exit_ready: bool = False


_CLEANUP_ERROR = "Cleanup failed; restart the application before starting again."
_RETRY_DELAYS = (1, 2, 4, 8, 16)


def _wait(cancel: Event, seconds: float) -> bool:
    return cancel.wait(seconds)


class Coordinator:
    """One worker; explicit Start only, with cancellable waits and backpressure.

    Application integration must supply SimulatedTransport, never a USB adapter.
    The wait seam must honor cancellation and return True when cancelled; only
    deterministic tests should replace Event.wait. Counters are lifetime totals.
    """

    def __init__(self, store: SettingsStore,
                 source_factory: Callable[[Settings], SourceSession],
                 transport_factory: Callable[[], Transport] | None = None, *,
                 transport_context_factory: Callable[[StartContext], Transport] | None = None,
                 inventory_provider=None,
                 wait: Callable[[Event, float], bool] = _wait):
        if (transport_factory is None) == (transport_context_factory is None):
            raise TypeError("Provide exactly one transport factory path.")
        self._transport_context_factory = transport_context_factory
        self._inventory_provider = inventory_provider
        self._store = store
        self._source_factory = source_factory
        self._transport_factory = transport_factory
        self._wait = wait
        self._lock = Lock()
        self._cancel = Event()
        self._worker: Thread | None = None
        self._status = Snapshot()
        self._outcome = "stopped"
        self._cleanup_failed = False

    def _update(self, **changes):
        with self._lock:
            self._status = replace(self._status, **changes)

    def _reap_locked(self):
        # Only an observer of a *completed* thread may acknowledge Stop/Exit.
        if self._worker is not None and not self._worker.is_alive():
            self._worker = None
            changes = {"state": self._outcome, "worker_alive": False}
            if self._outcome == "stopped":
                changes.update(source_state="stopped", output_state="simulated-closed",
                               live_connected=None, data_stale=None, error=None)
            self._status = replace(self._status, **changes)
        self._status = replace(
            self._status,
            exit_ready=(self._status.exit_requested and self._worker is None
                        and not self._cleanup_failed),
        )

    def snapshot(self) -> Snapshot:
        with self._lock:
            self._reap_locked()
            return self._status

    def start(self) -> bool:
        """Start explicitly; False if a worker still exists, including stopping."""
        with self._lock:
            self._reap_locked()
            if self._status.exit_requested:
                raise LifecycleError("Exit has been requested.")
            if self._cleanup_failed:
                raise LifecycleError(_CLEANUP_ERROR)
            if self._worker is not None:
                return False
            settings = self._store.load()
            if settings is None:
                raise LifecycleError("Configure a MARS URL before starting.")
            if settings.output_mode == "native":
                raise LifecycleError("Native output is configured but is not enabled in this build. Select Simulation explicitly.")
            self._cancel = Event()
            self._outcome = "stopped"
            self._status = replace(self._status, state="starting", source_state="starting",
                                   live_connected=None, data_stale=None, error=None,
                                   worker_alive=True)
            context = StartContext(settings, self._cancel)
            self._worker = Thread(target=self._run, args=(context,),
                                  name="mars-display-capture", daemon=False)
            try:
                self._worker.start()
            except RuntimeError:
                self._worker = None
                self._status = replace(self._status, state="error", worker_alive=False,
                                       error="Cannot start capture worker; try Start again.")
                raise LifecycleError(self._status.error) from None
            return True

    def _stop_locked(self):
        self._reap_locked()
        if self._worker is not None:
            self._cancel.set()
            self._status = replace(self._status, state="stopping")
        elif not self._cleanup_failed:
            self._status = replace(self._status, state="stopped", source_state="stopped",
                                   live_connected=None, data_stale=None, error=None)

    def stop(self) -> None:
        """Nonblocking request. Poll snapshot for acknowledgement after cleanup."""
        with self._lock:
            self._stop_locked()

    def request_exit(self) -> None:
        """Nonblocking; GUI may exit when snapshot.exit_ready becomes True."""
        with self._lock:
            self._status = replace(self._status, exit_requested=True)
            self._stop_locked()
            self._reap_locked()

    def wait_stopped(self, timeout: float) -> bool:
        """Bounded non-GUI helper: True means thread finished, not clean cleanup.

        Inspect snapshot.state/error afterwards. Never call this on the UI thread.
        """
        if timeout < 0:
            raise ValueError("Timeout must be non-negative.")
        with self._lock:
            worker = self._worker
        if worker is not None:
            worker.join(timeout)
        return not self.snapshot().worker_alive

    def _configuration_stopped_locked(self):
        self._reap_locked()
        if (self._status.state != "stopped" or self._worker is not None
                or self._status.exit_requested):
            raise LifecycleError("Settings can be saved only while stopped.")

    def _configuration_selection_locked(self, settings):
        checked = _checked(settings)
        if checked.output_mode == "native":
            # P3's exact fresh selection rule; importing/resolving never opens a port.
            from .usb_worker import _resolve
            provider = self._inventory_provider if self._inventory_provider is not None else enumerate_devices
            try:
                _resolve(provider)
            except Exception:
                raise SettingsError(
                    "Selected native screen is unavailable or ambiguous; refresh selection before saving."
                ) from None
        return checked

    def save_settings(self, settings: Settings) -> None:
        """Serialize stopped admission, fresh selection and ordinary Save."""
        with self._lock:
            self._configuration_stopped_locked()
            self._store.save(self._configuration_selection_locked(settings))

    def migrate_settings(self, settings: Settings, *, acknowledge_legacy_incompatibility=False) -> None:
        """Explicit incompatible migration under the same authority as Start."""
        with self._lock:
            self._configuration_stopped_locked()
            if acknowledge_legacy_incompatibility is not True:
                raise SettingsError(_ACK_ERROR) from None
            checked = self._configuration_selection_locked(settings)
            self._store.migrate_to_v2(checked, acknowledge_legacy_incompatibility=True)

    def restore_schema1_settings(self) -> None:
        with self._lock:
            self._configuration_stopped_locked()
            self._store.restore_schema1()

    def export_schema1_settings(self, destination) -> None:
        with self._lock:
            self._configuration_stopped_locked()
            self._store.export_schema1(destination)

    def _cleanup(self, source, output) -> bool:
        failed = False
        # Try both even if the first close fails; never clear/reset the output.
        for resource in (source, output):
            if resource is not None:
                try:
                    resource.close()
                except Exception:
                    failed = True
        if failed:
            with self._lock:
                self._cleanup_failed = True
                self._status = replace(self._status, output_state="error", error=_CLEANUP_ERROR)
        else:
            with self._lock:
                if self._status.output_state != "error":
                    self._status = replace(self._status, output_state="simulated-closed")
        return not failed

    def _run(self, context: StartContext):
        settings, cancel = context.settings, context.cancel
        consecutive = 0
        outcome = "stopped"
        try:
            while not cancel.is_set():
                source = output = None
                stage = "source"
                failed = False
                try:
                    self._update(source_state="starting", live_connected=None, data_stale=None)
                    source = self._source_factory(settings)
                    if cancel.is_set():
                        break
                    source.open()
                    if cancel.is_set():
                        break
                    stage = "output"
                    output = (self._transport_context_factory(context)
                              if self._transport_context_factory is not None
                              else self._transport_factory())
                    if cancel.is_set():
                        break
                    output.open()
                    self._update(output_state="simulated-open")
                    while not cancel.is_set():
                        started = monotonic()
                        stage = "source"
                        sample = source.read()
                        if cancel.is_set():
                            break
                        if not isinstance(sample, SourceSample):
                            raise TypeError("Source must return SourceSample.")
                        self._update(source_state=sample.state,
                                     live_connected=sample.live_connected, data_stale=sample.data_stale)
                        if sample.frame is not None:
                            stage = "output"
                            if cancel.is_set():
                                break
                            output.send(sample.frame)
                            with self._lock:
                                self._status = replace(self._status, latest_frame=sample.frame,
                                                       frames_sent=self._status.frames_sent + 1)
                        consecutive = 0
                        with self._lock:
                            if not cancel.is_set():
                                self._status = replace(self._status, state="running", error=None)
                        # No queue: at most one synchronous capture/write at a time.
                        if self._wait(cancel, max(0, 1 - (monotonic() - started))):
                            break
                except Exception:
                    failed = True
                    with self._lock:
                        changes = {"failures": self._status.failures + 1}
                        if stage == "source":
                            changes.update(source_state="error", live_connected=None, data_stale=None)
                        else:
                            changes.update(output_state="error")
                        self._status = replace(self._status, **changes)
                finally:
                    clean = self._cleanup(source, output)
                if not clean:
                    outcome = "error"
                    break
                if cancel.is_set() or not failed:
                    break
                if consecutive == len(_RETRY_DELAYS):
                    self._update(error="Recovery exhausted; check MARS and output, then Start.")
                    outcome = "error"
                    break
                with self._lock:
                    if cancel.is_set():
                        break
                    self._status = replace(self._status, state="retrying",
                                           retries=self._status.retries + 1,
                                           error="Capture or output failed; retrying.")
                if self._wait(cancel, _RETRY_DELAYS[consecutive]):
                    break
                consecutive += 1
        except Exception:
            # A faulty injected wait must not strand a completed worker as running.
            outcome = "error"
            self._update(error="Capture worker failed; check configuration, then Start.")
        finally:
            with self._lock:
                self._outcome = "error" if self._cleanup_failed else outcome
