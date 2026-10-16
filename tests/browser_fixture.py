"""Loopback-only test fixture, independent of application/browser dependencies."""
from collections import Counter
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import socket
from threading import Event, Lock, Thread, local
from time import monotonic
from unittest.mock import patch
from uuid import uuid4


@dataclass(frozen=True)
class TraceEvent:
    case: str
    generation: str
    time: float
    kind: str
    method: str = ""
    path: str = ""
    peer: tuple = ()
    headers: tuple = ()
    request_id: int | None = None
    navigation_id: int | None = None
    provenance: str = "socket peer only; client process unknown"
    details: tuple = ()
    ownership: str = "unattributed"


@dataclass(frozen=True)
class Snapshot:
    counts: tuple
    events: tuple
    active_threads: int
    active_connections: int
    closed: bool
    owned_counts: tuple
    foreign_counts: tuple


class BrowserFixture:
    """One case/generation owns its listener, HTML, counts, sessions and trace.

    start()/close() or a context manager; own(session) registers every replacement.
    snapshot() is an immutable atomic observation; no reset/filter API exists.
    before_response(fixture, path) is a test-only handshake seam: it MUST use
    bounded waits and honor fixture.stopping. Socket reads are bounded to 0.5s.
    instrument(Page, Route) scopes API tracing without importing Playwright.
    """

    def __init__(self, case, html, *, before_response=None):
        self.case, self.generation = case, uuid4().hex[:12]
        self._lock = Lock()
        self._html = html
        self._counts, self._events = Counter(), []
        self._owned_counts, self._foreign_counts = Counter(), Counter()
        self._identity = uuid4().hex
        self._workers, self._connections, self._sessions = [], set(), []
        self.stopping = Event()
        self._server = self._thread = None
        self._closed = False
        self.cleanup_seconds = 0
        self.before_response = before_response

    @property
    def request_headers(self):
        """Fresh copy of the opaque test marker; not authentication/PID proof."""
        return {"X-MarsDisplay-Test-Case": self._identity}

    def _ownership(self, headers):
        return "owned" if headers.get("X-MarsDisplay-Test-Case") == self._identity else "foreign"

    @property
    def html(self):
        with self._lock:
            return self._html

    @html.setter
    def html(self, value):
        with self._lock:
            self._html = value

    def _event(self, kind, **fields):
        with self._lock:
            self._events.append(TraceEvent(self.case, self.generation, monotonic(), kind, **fields))

    def snapshot(self):
        with self._lock:
            return Snapshot(tuple(sorted(self._counts.items())), tuple(self._events),
                            sum(t.is_alive() for t in self._workers)
                            + int(self._thread is not None and self._thread.is_alive()),
                            len(self._connections), self._closed,
                            tuple(sorted(self._owned_counts.items())),
                            tuple(sorted(self._foreign_counts.items())))

    def own(self, session):
        if not any(old is session for old in self._sessions):
            self._sessions.append(session)
        return session

    def start(self):
        fixture = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                fields = dict(method=self.command, path=self.path,
                              peer=tuple(self.client_address), headers=tuple(self.headers.items()),
                              ownership=fixture._ownership(self.headers))
                with fixture._lock:
                    fixture._counts[self.path] += 1
                    partition = (fixture._owned_counts if fields["ownership"] == "owned"
                                 else fixture._foreign_counts)
                    partition[self.path] += 1
                    fields["request_id"] = sum(fixture._counts.values())
                    fixture._events.append(TraceEvent(fixture.case, fixture.generation,
                                                      monotonic(), "handler.start", **fields))
                details = ()
                try:
                    if fixture.before_response:
                        fixture.before_response(fixture, self.path)
                    redirect = self.path == "/disabled/display"
                    body = b"" if redirect else fixture.html.encode()
                    self.send_response(302 if redirect else 200)
                    if redirect:
                        self.send_header("Location", "/")
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    details = (("status", 302 if redirect else 200),)
                except Exception as error:
                    details = (("error", type(error).__name__),)
                finally:
                    fixture._event("handler.end", **fields, details=details)

            def log_message(self, *args):
                pass

        class Server(ThreadingHTTPServer):
            # Explicit bounded joins below, never daemon-thread abandonment.
            block_on_close = False

            def get_request(self):
                connection, address = super().get_request()
                connection.settimeout(0.5)
                return connection, address

            def process_request(self, connection, address):
                def run():
                    try:
                        self.process_request_thread(connection, address)
                    finally:
                        with fixture._lock:
                            fixture._connections.discard(connection)
                worker = Thread(target=run, name=f"fixture-handler-{fixture.generation}")
                with fixture._lock:
                    fixture._connections.add(connection)
                    fixture._workers.append(worker)
                    worker.start()

        self._server = Server(("127.0.0.1", 0), Handler)
        self.port = self._server.server_port
        self.url = f"http://127.0.0.1:{self.port}"
        self._thread = Thread(target=lambda: self._server.serve_forever(poll_interval=0.01),
                              name=f"fixture-server-{self.generation}")
        self._thread.start()
        return self

    def close(self):
        if self._closed:
            return
        started = monotonic()
        errors = []
        for session in reversed(self._sessions):
            try:
                session.close()
            except Exception as error:
                errors.append(error)
        self.stopping.set()
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            with self._lock:
                connections = tuple(self._connections)
                workers = tuple(self._workers)
            for connection in connections:
                try:
                    connection.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                connection.close()
            deadline = monotonic() + 1.5
            for worker in (*workers, self._thread):
                worker.join(max(0, deadline - monotonic()))
            if any(worker.is_alive() for worker in (*workers, self._thread)):
                errors.append(RuntimeError("fixture threads did not drain within 1.5 seconds"))
        with self._lock:
            self._closed = not errors
        self.cleanup_seconds = monotonic() - started
        if errors:
            raise RuntimeError(f"fixture cleanup failed: {errors!r}; {self.snapshot()!r}")

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.close()

    @contextmanager
    def instrument(self, Page, Route):
        """Trace and tag only pages navigated inside this test scope.

        A last-installed fallback route retains the page's existing routing and
        headers. Fetch/continue overrides retain options and explicit markers.
        Navigation IDs and opaque markers are NOT socket/process identity.
        """
        state = local()
        serial = 0
        goto, fetch, continue_request = Page.goto, Route.fetch, Route.continue_
        provenance = "test API observation; not socket process identity"
        pages, owners, requests = {}, {}, {}

        def metadata(request, navigation_id):
            # Read public, locally available metadata when first observed, not
            # from a request/frame after its browser or driver has stopped.
            if request not in requests:
                requests[request] = dict(method=request.method, path=request.url,
                                         headers=tuple(request.headers.items()),
                                         navigation_id=navigation_id, ownership="owned")
            return requests[request]

        def record(kind, fields=None, **details):
            self._event(kind, **(fields or {}), provenance=provenance,
                        details=tuple(details.items()))

        def response_details(response):
            return dict(status=response.status, location=response.headers.get("location"))

        def detach(page):
            entry = pages[page]
            for event, callback in reversed(tuple(entry["listeners"])):
                page.remove_listener(event, callback)
                entry["listeners"].remove((event, callback))
            if entry.get("tagger") is not None:
                page.unroute("**/*", entry["tagger"])
                entry["tagger"] = None

        def protect_close(owner, page):
            if owner in owners:
                owners[owner].append(page)
                return
            owners[owner] = [page]
            close = owner.close

            def closing(*args, **kwargs):
                # Explicit ownership: detach before ANY owned close can tear
                # down the live subscription channel, including failed setup.
                for owned_page in owners[owner]:
                    detach(owned_page)
                return close(*args, **kwargs)

            patches.enter_context(patch.object(owner, "close", closing))

        def attach(page, navigation_id):
            if page in pages:
                pages[page]["navigation"] = navigation_id
                return
            entry = pages[page] = dict(navigation=navigation_id, listeners=[])

            def tag_request(route):
                # Installed last: fallback retains existing route handlers/options.
                route.fallback(**tagged_options(route, {}))

            page.route("**/*", tag_request)
            entry["tagger"] = tag_request

            def request_seen(request):
                record("page.request", metadata(request, entry["navigation"]))

            def response_seen(response):
                request = getattr(response, "request", None)
                fields = (metadata(request, entry["navigation"]) if request is not None
                          else dict(navigation_id=entry["navigation"]))
                record("page.response", fields, **response_details(response))

            for owner in (page, page.context, page.context.browser):
                if owner is not None:
                    protect_close(owner, page)
            for event, callback in (
                ("request", request_seen), ("response", response_seen),
                ("framenavigated", lambda frame: record(
                    "page.navigation", dict(navigation_id=entry["navigation"]), url=frame.url)),
            ):
                page.on(event, callback)
                entry["listeners"].append((event, callback))

        def traced_goto(page, url, *args, **kwargs):
            nonlocal serial
            serial += 1
            previous = getattr(state, "navigation", None)
            state.navigation = serial
            try:
                attach(page, serial)
                record("page.goto.begin", dict(navigation_id=serial), url=url)
                return goto(page, url, *args, **kwargs)
            finally:
                record("page.goto.end", dict(navigation_id=state.navigation), url=url)
                state.navigation = previous

        def request_headers(request):
            return request.all_headers() if hasattr(request, "all_headers") else request.headers

        def tagged_options(route, kwargs):
            supplied = kwargs.get("headers")
            headers = dict(supplied if supplied is not None else request_headers(route.request))
            marker_keys = [key for key in headers if key.lower() == "x-marsdisplay-test-case"]
            if marker_keys:
                # Preserve the last caller override, even with different casing.
                for key in marker_keys[:-1]:
                    del headers[key]
            else:
                headers.update(self.request_headers)
            return {**kwargs, "headers": headers}

        def traced_continue(route, *args, **kwargs):
            if route.request.frame.page in pages:
                kwargs = tagged_options(route, kwargs)
            return continue_request(route, *args, **kwargs)

        def traced_fetch(route, *args, **kwargs):
            if route.request.frame.page not in pages:
                return fetch(route, *args, **kwargs)
            kwargs = tagged_options(route, kwargs)
            fields = metadata(route.request, getattr(state, "navigation", None))
            record("route.fetch.begin", fields)
            try:
                response = fetch(route, *args, **kwargs)
            except Exception as error:
                record("route.fetch.end", fields, error=type(error).__name__)
                raise
            record("route.fetch.end", fields, **response_details(response))
            return response

        with ExitStack() as patches:
            patches.enter_context(patch.object(Page, "goto", traced_goto))
            patches.enter_context(patch.object(Route, "fetch", traced_fetch))
            patches.enter_context(patch.object(Route, "continue_", traced_continue))
            try:
                yield
            finally:
                # Also handles scope exit before explicit session close.
                for page in pages:
                    detach(page)
