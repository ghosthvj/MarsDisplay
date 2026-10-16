"""Public Playwright regression; no pending application-source dependency."""
from collections import Counter
from http.client import HTTPConnection
import unittest

from playwright.sync_api import Page, Route, sync_playwright

from browser_fixture import BrowserFixture


class S14TraceProbe(unittest.TestCase):
    def test_explicit_other_case_identity_remains_foreign(self):
        with BrowserFixture('current', '<body>ok</body>') as fixture, BrowserFixture('other', 'other') as other:
            foreign = other.request_headers
            with sync_playwright() as driver:
                browser = driver.chromium.launch(headless=True, chromium_sandbox=True, timeout=1500)
                try:
                    page = browser.new_page(extra_http_headers=foreign)
                    page.set_default_timeout(1500)

                    def forward(route):
                        route.fulfill(response=route.fetch(headers={**route.request.all_headers(), **foreign}, max_redirects=0, timeout=1500))

                    page.route('**/*', forward)
                    with fixture.instrument(Page, Route):
                        page.goto(fixture.url+'/foreign-navigation', wait_until='domcontentloaded')
                        page.evaluate("async () => (await fetch('/foreign-fetch')).text()")
                finally:
                    browser.close()
        snapshot = fixture.snapshot()
        paths = ('/foreign-navigation', '/foreign-fetch')
        starts = [event for event in snapshot.events if event.kind == 'handler.start' and event.path in paths]
        self.assertEqual(len(starts), 2, snapshot)
        expected = next(iter(foreign.values()))
        for event in starts:
            headers = {key.lower(): value for key, value in event.headers}
            self.assertEqual(headers['x-marsdisplay-test-case'], expected, snapshot)
            self.assertEqual(event.ownership, 'foreign', snapshot)
        for path in paths:
            self.assertEqual(dict(snapshot.counts)[path], 1, snapshot)
            self.assertEqual(dict(snapshot.foreign_counts)[path], 1, snapshot)
            self.assertNotIn(path, dict(snapshot.owned_counts), snapshot)

    def test_owned_browser_and_foreign_root_remain_strict_and_visible(self):
        original_goto, original_fetch, original_continue = Page.goto, Route.fetch, Route.continue_
        observed = []
        with BrowserFixture("S14-late-capture", "<body>fixture</body>") as fixture:
            connection = HTTPConnection("127.0.0.1", fixture.port, timeout=2)
            try:
                connection.request("GET", "/", headers={"User-Agent": "Go-http-client/1.1"})
                response = connection.getresponse()
                self.assertEqual((response.status, response.read()), (200, b"<body>fixture</body>"))
            finally:
                connection.close()
            with sync_playwright() as driver:
                browser = driver.chromium.launch(
                    headless=True, chromium_sandbox=True, timeout=1500)
                try:
                    page = browser.new_page(extra_http_headers={"X-Context": "context"})
                    page.set_extra_http_headers({"X-Page": "page"})
                    page.set_default_timeout(1500)

                    def route_request(route):
                        if route.request.is_navigation_request():
                            route.fulfill(response=route.fetch(
                                headers={**route.request.all_headers(), "X-Route": "route"},
                                max_redirects=0, timeout=1500))
                        else:
                            route.continue_(headers={**route.request.all_headers(), "X-Continue": "continued"})

                    page.route("**/*", route_request)
                    page.on("request", lambda request: observed.append(request.url))
                    with fixture.instrument(Page, Route):
                        page.goto(fixture.url + "/display", wait_until="domcontentloaded")
                        self.assertEqual(fixture.snapshot().owned_counts, (("/display", 1),), fixture.snapshot())
                        marker = len(fixture.snapshot().events)
                        page.set_viewport_size({"width": 480, "height": 320})
                        self.assertEqual(page.evaluate("async () => (await fetch('/')).status"), 200)
                        page.screenshot(timeout=1500)
                        before_extra = fixture.snapshot()
                        self.assertEqual(before_extra.owned_counts, (("/", 1), ("/display", 1)), before_extra)
                        self.assertEqual(page.evaluate("async () => (await fetch('/')).status"), 200)
                        self.assertEqual(fixture.snapshot().owned_counts, (("/", 2), ("/display", 1)), fixture.snapshot())
                    self.assertIs(Page.goto, original_goto)
                    self.assertIs(Route.fetch, original_fetch)
                    self.assertIs(Route.continue_, original_continue)
                    # Existing route/listener/header settings survive scope exit.
                    self.assertEqual(page.evaluate("async () => (await fetch('/restored')).status"), 200)
                finally:
                    browser.close()
        snapshot = fixture.snapshot()
        self.assertEqual(snapshot.owned_counts, (("/", 2), ("/display", 1)), snapshot)
        self.assertEqual((snapshot.active_threads, snapshot.active_connections), (0, 0))
        starts = [e for e in snapshot.events if e.kind == "handler.start"]
        self.assertEqual(Counter(dict(snapshot.counts)), Counter(e.path for e in starts), snapshot)
        for ownership, counts in (("owned", snapshot.owned_counts), ("foreign", snapshot.foreign_counts)):
            self.assertEqual(Counter(dict(counts)), Counter(e.path for e in starts if e.ownership == ownership), snapshot)
        self.assertEqual(Counter(dict(snapshot.counts)), Counter(dict(snapshot.owned_counts)) + Counter(dict(snapshot.foreign_counts)), snapshot)
        self.assertGreaterEqual(dict(snapshot.foreign_counts)["/"], 1, snapshot)
        self.assertEqual(dict(snapshot.foreign_counts)["/restored"], 1, snapshot)
        owned = [e for e in starts if e.ownership == "owned"]
        for event in owned:
            headers = {key.lower(): value for key, value in event.headers}
            self.assertEqual((headers["x-context"], headers["x-page"]), ("context", "page"), snapshot)
        self.assertEqual(dict((key.lower(), value) for key, value in owned[0].headers)["x-route"], "route", snapshot)
        for event in owned[1:]:
            self.assertEqual(dict((key.lower(), value) for key, value in event.headers)["x-continue"], "continued", snapshot)
        restored = next(e for e in starts if e.path == "/restored")
        restored_headers = {key.lower(): value for key, value in restored.headers}
        self.assertNotIn("x-marsdisplay-test-case", restored_headers, snapshot)
        self.assertEqual((restored_headers["x-context"], restored_headers["x-page"], restored_headers["x-continue"]),
                         ("context", "page", "continued"), snapshot)
        self.assertIn(fixture.url + "/restored", observed)
        self.assertTrue(any(e.kind == "page.request" and e.path == fixture.url + "/" for e in snapshot.events[marker:]), snapshot)
        self.assertTrue(any(e.kind == "route.fetch.end" and dict(e.details)["status"] == 200 for e in snapshot.events), snapshot)


if __name__ == "__main__":
    unittest.main()
