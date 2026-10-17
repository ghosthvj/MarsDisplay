"""Worker-owned, bundled Chromium capture of the version 1 MARS display.

No profile, credentials, remote-debugging attachment, API client or disk images.
All methods must be called on the same coordinator worker.
"""
from io import BytesIO
import os
from time import monotonic

from PIL import Image
from playwright.sync_api import (
    Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError, sync_playwright,
)

from .frames import RGBFrame
from .lifecycle import SourceSample
from .settings import Settings


class BrowserError(RuntimeError):
    """Actionable public failure, never containing backend messages or URLs."""


_TIMEOUT = 1500  # Each backend navigation/readiness/screenshot operation, in ms.
_METADATA_ERROR = "MARS display metadata is missing or incompatible; enable the version 1 display endpoint."
_OPEN_ERROR = "Cannot open the bundled browser display; check browser availability and direct MARS access."
_CAPTURE_ERROR = "Cannot capture the MARS display; check layout, fonts and direct access, then retry."
_GEOMETRY_ERROR = "MARS display geometry does not match its orientation; check display layout."

_METADATA = """() => {
    const roots = document.querySelectorAll('#mars-display');
    if (roots.length !== 1) return null;
    const r = roots[0], b = r.getBoundingClientRect();
    return {version:r.dataset.displayVersion, state:r.dataset.displayState,
        orientation:r.dataset.orientation, width:r.dataset.width, height:r.dataset.height,
        server:r.dataset.serverId, live:r.dataset.liveConnected, stale:r.dataset.dataStale,
        x:b.x + scrollX, y:b.y + scrollY, w:b.width, h:b.height,
        visible:!!r.getClientRects().length && getComputedStyle(r).visibility === 'visible',
        fonts:document.fonts.status};
}"""

_SETTLED = """() => {
    const r = document.querySelector('#mars-display');
    if (!r || document.fonts.status !== 'loaded') return false;
    const promise = document.fonts.ready;
    let fonts = window.__marsDisplayCaptureFonts;
    if (!fonts || fonts.promise !== promise) {
        fonts = {promise, ready:false};
        window.__marsDisplayCaptureFonts = fonts;
        promise.then(() => {fonts.ready=true;});
        return false;
    }
    if (!fonts.ready) return false;
    const b = r.getBoundingClientRect();
    const key = JSON.stringify([b.x,b.y,b.width,b.height]);
    const old = window.__marsDisplayCaptureLayout;
    window.__marsDisplayCaptureLayout = {key, count:old && old.key===key ? old.count+1 : 0};
    return window.__marsDisplayCaptureLayout.count >= 2;
}"""


class BrowserSession:
    """Synchronous SourceSession: open(), read() -> SourceSample, close().

    Open is idempotent. Read never navigates or polls an API. Failures are raised
    for coordinator recovery; loading/empty are observations without frames.
    Close releases only this session's isolated browser and driver, including
    after partial setup. Capture failures leave cleanup to the coordinator.
    """

    def __init__(self, settings: Settings):
        self._url = settings.capture_url
        self._driver = self._browser = self._context = self._page = None

    def open(self) -> None:
        if self._page is not None:
            return
        try:
            # Resolve only Playwright's package/bundle-local browser. Do not use
            # installed Chrome, a persistent profile, or a fallback executable.
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "0"
            self._driver = sync_playwright().start()
            self._browser = self._driver.chromium.launch(
                headless=True, chromium_sandbox=True, timeout=_TIMEOUT)
            self._context = self._browser.new_context(
                viewport={"width": 320, "height": 480}, device_scale_factor=1,
                service_workers="block")
            self._context.set_default_timeout(_TIMEOUT)
            self._context.set_default_navigation_timeout(_TIMEOUT)
            self._page = self._context.new_page()

            def reject_extra_page(page):
                if page is not self._page:
                    page.close()

            self._context.on("page", reject_extra_page)

            def route_navigation(route):
                request = route.request
                try:
                    owned_frame = request.frame is self._page.main_frame
                except PlaywrightError:
                    # A popup's first request can precede its frame. Reject it
                    # before any traffic, not only after the page event fires.
                    owned_frame = False
                if not owned_frame:
                    route.abort()
                    return
                if not request.is_navigation_request():
                    route.continue_()
                    return
                if request.url != self._url:
                    route.abort()
                    return
                try:
                    # Playwright routes only the first request of a redirect
                    # chain. Inspect that response without following redirects,
                    # then fulfill the original navigation (one HTTP request).
                    response = route.fetch(max_redirects=0, timeout=_TIMEOUT)
                    if response.ok:
                        route.fulfill(response=response)
                    else:
                        route.abort()
                except Exception:
                    route.abort()

            # Block redirects/login navigation *before* contacting another path
            # or origin, including popup/subframe credential flows.
            self._context.route("**/*", route_navigation)
            response = self._page.goto(self._url, wait_until="domcontentloaded", timeout=_TIMEOUT)
            if response is None or not response.ok or self._page.url != self._url:
                raise BrowserError(_OPEN_ERROR)
        except Exception:
            # Retain any resource that fails to close so coordinator.close can
            # retry and latch uncertain cleanup rather than losing ownership.
            try:
                self.close()
            except BrowserError:
                raise BrowserError("Browser setup cleanup failed; restart MarsDisplay before retrying.") from None
            raise BrowserError(_OPEN_ERROR) from None

    def _metadata(self):
        if self._page.url != self._url:
            raise BrowserError("MARS left the configured display path; check direct display access.")
        # SPA mounting may follow DOMContentLoaded. Wait only for root presence;
        # duplicates or incompatible existing metadata must fail immediately.
        try:
            handle = self._page.wait_for_function(
                "() => document.querySelectorAll('#mars-display').length === 0 "
                "? false : ({data:(" + _METADATA + ")()})", timeout=_TIMEOUT)
        except PlaywrightTimeoutError:
            raise BrowserError(_METADATA_ERROR) from None
        try:
            data = handle.json_value()["data"]
        finally:
            handle.dispose()
        if self._page.url != self._url:
            raise BrowserError("MARS left the configured display path; check direct display access.")
        if not data or data.get("version") != "1":
            raise BrowserError(_METADATA_ERROR)
        geometry = {"portrait": ("320", "480"), "landscape": ("480", "320")}
        size = geometry.get(data.get("orientation"))
        if (size is None or (data.get("width"), data.get("height")) != size
                or data.get("state") not in {"loading", "ready", "empty", "error"}
                or data.get("live") not in {"true", "false"}
                or data.get("stale") not in {None, "true", "false"}
                or (data["state"] == "ready" and not (data.get("server") or "").strip())):
            raise BrowserError(_METADATA_ERROR)
        if data["state"] == "error":
            raise BrowserError("MARS reports a display error; check its display configuration.")
        return data

    @staticmethod
    def _sample(data, frame=None):
        return SourceSample(data["state"], frame, data["live"] == "true",
                            None if data.get("stale") is None else data["stale"] == "true")

    def read(self) -> SourceSample:
        if self._page is None:
            raise BrowserError("Open the browser session before reading.")
        try:
            data = self._metadata()
            if data["state"] != "ready":
                return self._sample(data)
            size = {"width": int(data["width"]), "height": int(data["height"])}
            if self._page.viewport_size != size:
                self._page.set_viewport_size(size)
            # Fonts and three matching animation-frame layout observations are
            # bounded; no network-idle wait (MARS keeps an SSE connection).
            settled_handle = self._page.wait_for_function(_SETTLED, polling="raf", timeout=_TIMEOUT)
            settled_handle.dispose()
            before = self._metadata()
            if before["state"] != "ready" or any(before[k] != data[k] for k in
                                                      ("orientation", "width", "height", "server")):
                return self._sample(before)
            if (not before["visible"] or before["w"] != size["width"]
                    or before["h"] != size["height"] or before["x"] < 0 or before["y"] < 0):
                raise BrowserError(_GEOMETRY_ERROR)
            png = self._page.screenshot(type="png", timeout=_TIMEOUT,
                                       clip={"x": before["x"], "y": before["y"],
                                             "width": before["w"], "height": before["h"]})
            captured_at = monotonic()
            after = self._metadata()
            if before != after:
                return self._sample(after)
            with Image.open(BytesIO(png)) as image:
                if image.size != (size["width"], size["height"]):
                    raise BrowserError(_GEOMETRY_ERROR)
                rgb = image.convert("RGB").tobytes()
            return self._sample(after, RGBFrame(size["width"], size["height"], rgb, captured_at))
        except BrowserError:
            raise
        except Exception:
            raise BrowserError(_CAPTURE_ERROR) from None

    def close(self) -> None:
        failed = False
        # Browser.close owns its contexts/pages; driver.stop owns its child
        # driver. Never enumerate processes or terminate an external browser.
        for attribute, method in (("_browser", "close"), ("_driver", "stop")):
            resource = getattr(self, attribute)
            if resource is not None:
                try:
                    getattr(resource, method)()
                except Exception:
                    failed = True
                else:
                    setattr(self, attribute, None)
        if self._browser is None:
            self._context = self._page = None
        if failed:
            raise BrowserError("Cannot close the owned browser session; restart MarsDisplay before retrying.") from None
