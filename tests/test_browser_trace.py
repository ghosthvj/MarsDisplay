"""Public Playwright regression; no pending application-source dependency."""
import unittest

from playwright.sync_api import Page, Route, sync_playwright

from browser_fixture import BrowserFixture


class S13TraceProbe(unittest.TestCase):
    def test_late_browser_request_is_present_in_public_trace(self):
        original_goto, original_fetch = Page.goto, Route.fetch
        observed = []
        with BrowserFixture("S13-late-capture", "<body>fixture</body>") as fixture:
            with fixture.instrument(Page, Route):
                with sync_playwright() as driver:
                    browser = driver.chromium.launch(
                        headless=True, chromium_sandbox=True, timeout=1500)
                    try:
                        page = browser.new_page()
                        page.set_default_timeout(1500)

                        def route_request(route):
                            if route.request.is_navigation_request():
                                route.fulfill(response=route.fetch(max_redirects=0, timeout=1500))
                            else:
                                route.continue_()

                        page.route("**/*", route_request)
                        page.on("request", lambda request: observed.append(request.url))
                        page.goto(fixture.url + "/display", wait_until="domcontentloaded")
                        marker = len(fixture.snapshot().events)
                        page.set_viewport_size({"width": 480, "height": 320})
                        status = page.evaluate("async () => (await fetch('/')).status")
                        page.screenshot(timeout=1500)
                    finally:
                        browser.close()
        self.assertIs(Page.goto, original_goto)
        self.assertIs(Route.fetch, original_fetch)
        snapshot = fixture.snapshot()
        self.assertEqual(status, 200)
        self.assertEqual(snapshot.counts, (("/", 1), ("/display", 1)), fixture.snapshot())
        self.assertEqual((snapshot.active_threads, snapshot.active_connections), (0, 0))
        self.assertIn(fixture.url + "/", observed)
        late = snapshot.events[marker:]
        self.assertTrue(
            any(event.kind == "page.request" and event.path == fixture.url + "/" for event in late),
            "S13 missing Page request provenance after goto during later landscape capture")


if __name__ == "__main__":
    unittest.main()
