"""Real bundled Chromium against loopback only; no MARS or user profile."""
from collections import Counter
from pathlib import Path
from time import monotonic
import unittest
from unittest.mock import patch

from playwright.sync_api import Browser, Page, Route

from browser_fixture import BrowserFixture
from test_browser_security_regression import query_gated_html

from mars_display.browser import BrowserError, BrowserSession
from mars_display.settings import Settings


class BrowserTests(unittest.TestCase):
    def setUp(self):
        self.fixture = Path(__file__).with_name("fixtures").joinpath("display.html").read_text()
        self.fixture_server = self.enterContext(BrowserFixture(self.id(), self.fixture))
        self.enterContext(self.fixture_server.instrument(Page, Route))
        # LIFO: all sessions and handlers close before instrumentation is restored.
        self.addCleanup(self.fixture_server.close)
        self.url = self.fixture_server.url
        self.session = BrowserSession(Settings(self.url))

    @property
    def session(self):
        return self._session

    @session.setter
    def session(self, session):
        self._session = self.fixture_server.own(session)

    @property
    def requests(self):
        return Counter(dict(self.fixture_server.snapshot().owned_counts))

    @property
    def request_details(self):
        return self.fixture_server.snapshot()

    def test_persistent_ready_rgb_portrait_and_landscape(self):
        for landscape in (False, True):
            with self.subTest(landscape=landscape):
                if landscape:
                    self.session.close()
                    self.fixture_server.html = (self.fixture.replace("portrait", "landscape")
                                      .replace("320", "TEMP").replace("480", "320")
                                      .replace("TEMP", "480"))
                self.session.open()
                before = monotonic()
                first = self.session.read()
                second = self.session.read()
                size = (480, 320) if landscape else (320, 480)
                self.assertEqual(first.state, "ready")
                self.assertEqual((first.frame.width, first.frame.height), size)
                self.assertEqual(first.frame.rgb, bytes((17, 34, 51)) * (320 * 480))
                self.assertEqual(second.frame.rgb, first.frame.rgb)
                self.assertLessEqual(before, first.frame.captured_at)
                self.assertLessEqual(first.frame.captured_at, second.frame.captured_at)
                self.assertEqual((first.live_connected, first.data_stale), (True, False))
                self.assertEqual(self.requests, Counter({"/display": 1 + int(landscape)}),
                                 self.request_details)
                self.session.open()  # idempotent, never navigates again
                self.assertIsNotNone(self.session.read().frame)
                self.session.close()
                self.assertEqual(self.requests, Counter({"/display": 1 + int(landscape)}),
                                 self.request_details)
                events = self.fixture_server.snapshot().events
                fetches = [e for e in events if e.kind == "route.fetch.end"]
                self.assertEqual(len(fetches), 1 + int(landscape), events)
                self.assertTrue(all(dict(e.details)["status"] == 200 for e in fetches), events)
                self.assertTrue(all(e.navigation_id is not None for e in fetches), events)

    def test_loading_empty_and_independent_freshness(self):
        for state, live, stale in (("loading", "false", "true"), ("empty", "true", "false")):
            with self.subTest(state=state):
                self.session.close()
                self.fixture_server.html = (self.fixture.replace('state="ready"', f'state="{state}"')
                                  .replace('connected="true"', f'connected="{live}"')
                                  .replace('stale="false"', f'stale="{stale}"'))
                self.session.open()
                sample = self.session.read()
                self.assertEqual(sample.state, state)
                self.assertIsNone(sample.frame)
                self.assertEqual((sample.live_connected, sample.data_stale),
                                 (live == "true", stale == "true"))

    def test_stale_disconnected_ready_still_captures(self):
        self.fixture_server.html = (self.fixture.replace('connected="true"', 'connected="false"')
                          .replace('stale="false"', 'stale="true"'))
        self.session.open()
        sample = self.session.read()
        self.assertEqual(sample.state, "ready")
        self.assertIsNotNone(sample.frame)
        self.assertEqual((sample.live_connected, sample.data_stale), (False, True))

    def test_invalid_metadata_login_and_geometry_never_capture(self):
        cases = [
            ("<form><input type=password></form>", "MARS display metadata is missing or incompatible; enable the version 1 display endpoint."),
            (self.fixture.replace('version="1"', 'version="2"'), "MARS display metadata is missing or incompatible; enable the version 1 display endpoint."),
            (self.fixture.replace('data-server-id="fixture-server"', ''), "MARS display metadata is missing or incompatible; enable the version 1 display endpoint."),
            (self.fixture.replace('width="320"', 'width="480"'), "MARS display metadata is missing or incompatible; enable the version 1 display endpoint."),
            (self.fixture.replace('connected="true"', 'connected="unknown"'), "MARS display metadata is missing or incompatible; enable the version 1 display endpoint."),
            (self.fixture.replace('state="ready"', 'state="error"'), "MARS reports a display error; check its display configuration."),
            (self.fixture.replace("width:320px", "width:319px"), "MARS display geometry does not match its orientation; check display layout."),
        ]
        # Existing invalid roots must not be given time to become compatible.
        for html, repair in (
            (self.fixture.replace('version="1"', 'version="2"'), "document.getElementById('mars-display').dataset.displayVersion='1'"),
            (self.fixture.replace('state="ready"', 'state="invalid"'), "document.getElementById('mars-display').dataset.displayState='ready'"),
            (self.fixture.replace('</body>', "<script>document.body.append(document.getElementById('mars-display').cloneNode(true));</script></body>"), "document.getElementById('mars-display').remove()"),
        ):
            cases.append((query_gated_html(html, repair), "MARS display metadata is missing or incompatible; enable the version 1 display endpoint."))
        with patch.object(Page, "screenshot", side_effect=AssertionError("must not capture")):
            for html, message in cases:
                with self.subTest(message=message, html=html[:40]):
                    self.session.close()
                    self.fixture_server.html = html
                    self.session.open()
                    started = monotonic()
                    with self.assertRaises(BrowserError) as caught:
                        self.session.read()
                    self.assertEqual(str(caught.exception), message)
                    if html.startswith('<form>'):
                        self.assertGreaterEqual(monotonic() - started, 1.5)
        self.assertEqual(self.requests, Counter({'/display': len(cases)}), self.request_details)
        snapshot = self.request_details
        self.assertEqual(Counter(dict(snapshot.counts)), Counter(dict(snapshot.owned_counts)) + Counter(dict(snapshot.foreign_counts)), snapshot)

    def test_disabled_redirect_is_not_followed(self):
        self.session = BrowserSession(Settings(self.url + "/disabled"))
        with self.assertRaises(BrowserError) as caught:
            self.session.open()
        self.assertEqual(str(caught.exception), "Cannot open the bundled browser display; check browser availability and direct MARS access.")
        self.assertEqual(self.requests, Counter({"/disabled/display": 1}), self.request_details)
        events = self.fixture_server.snapshot().events
        fetches = [e for e in events if e.kind == "route.fetch.end"]
        self.assertEqual(len(fetches), 1, events)
        self.assertEqual(dict(fetches[0].details), {"status": 302, "location": "/"}, events)
        self.assertIsNotNone(fetches[0].navigation_id, events)
        self.session.close()

    def test_fonts_and_layout_settle_before_capture(self):
        self.fixture_server.html = self.fixture.replace("</body>", """<script>
        const root = document.querySelector('#mars-display');
        root.style.width = '319px';
        const ready = new Promise(resolve => {window.resolveFixtureFonts=resolve;});
        Object.defineProperty(document, 'fonts', {value: {status:'loading', ready}});
        setTimeout(() => { document.fonts.status = 'loaded'; root.style.width='320px';
                           window.resolveFixtureFonts(); }, 100);
        </script></body>""")
        self.session.open()
        self.assertEqual(self.session.read().frame.rgb, bytes((17, 34, 51)) * (320 * 480))

    def test_unsettled_fonts_timeout_is_sanitized(self):
        self.fixture_server.html = self.fixture.replace("</body>", """<script>
        Object.defineProperty(document, 'fonts', {
            value:{status:'loaded', ready:new Promise(() => {})}});
        </script></body>""")
        self.session.open()
        with self.assertRaises(BrowserError) as caught:
            self.session.read()
        self.assertEqual(str(caught.exception), "Cannot capture the MARS display; check layout, fonts and direct access, then retry.")

    def test_transition_during_screenshot_drops_frame(self):
        original = Page.screenshot
        for change in (
            "r.dataset.serverId='next'",
            "r.dataset.displayState='loading'",
            "r.dataset.orientation='landscape';r.dataset.width='480';r.dataset.height='320';r.style.width='480px';r.style.height='320px'",
        ):
            with self.subTest(change=change):
                self.session.close()
                self.session.open()

                def transitioning(page, *args, **kwargs):
                    png = original(page, *args, **kwargs)
                    page.evaluate("() => {const r=document.querySelector('#mars-display');" + change + "}")
                    return png

                with patch.object(Page, "screenshot", transitioning):
                    sample = self.session.read()
                self.assertIsNone(sample.frame)
                self.assertIn(sample.state, ("ready", "loading"))
                next_sample = self.session.read()
                if "orientation" in change:
                    self.assertEqual((next_sample.frame.width, next_sample.frame.height), (480, 320))

    def test_owned_browser_closes_on_setup_failure_and_close_is_repeatable(self):
        owned = []
        original = Browser.new_context

        def failing(browser, *args, **kwargs):
            owned.append(browser)
            raise RuntimeError("private-url-token")

        with patch.object(Browser, "new_context", failing):
            with self.assertRaises(BrowserError):
                self.session.open()
        self.assertEqual(len(owned), 1)
        self.assertFalse(owned[0].is_connected())
        self.session.close()
        self.session.close()
        with self.assertRaisesRegex(BrowserError, "^Open the browser session before reading.$"):
            self.session.read()
        with patch.object(Browser, "new_context", original):
            self.session.open()
            self.assertIsNotNone(self.session.read().frame)

    def test_capture_failure_is_sanitized_and_owned_browser_closes(self):
        owned = []
        original = Browser.new_context

        def recording(browser, *args, **kwargs):
            owned.append(browser)
            self.assertEqual(kwargs["device_scale_factor"], 1)
            self.assertNotIn("ignore_https_errors", kwargs)
            return original(browser, *args, **kwargs)

        with patch.object(Browser, "new_context", recording):
            self.session.open()
        with patch.object(Page, "screenshot", side_effect=RuntimeError("private-url-token")):
            with self.assertRaises(BrowserError) as caught:
                self.session.read()
        self.assertEqual(str(caught.exception), "Cannot capture the MARS display; check layout, fonts and direct access, then retry.")
        self.session.close()
        self.assertFalse(owned[0].is_connected())
        self.assertEqual(self.requests, Counter({"/display": 1}), self.request_details)


if __name__ == "__main__":
    unittest.main()
