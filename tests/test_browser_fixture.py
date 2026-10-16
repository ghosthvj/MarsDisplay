"""Standard-library fixture proofs; no browser, Qt or application imports."""
from collections import Counter
from http.client import HTTPConnection
from threading import Event, Thread
import unittest

from browser_fixture import BrowserFixture


def get(fixture, path="/display", headers=None):
    connection = HTTPConnection("127.0.0.1", fixture.port, timeout=2)
    try:
        connection.request("GET", path, headers=fixture.request_headers if headers is None else headers)
        response = connection.getresponse()
        return response.status, response.getheader("Location"), response.read()
    finally:
        connection.close()


class FixtureTests(unittest.TestCase):
    def assert_partition(self, snapshot):
        starts = [e for e in snapshot.events if e.kind == "handler.start"]
        self.assertEqual(Counter(dict(snapshot.counts)), Counter(e.path for e in starts), snapshot)
        for ownership, counts in (("owned", snapshot.owned_counts), ("foreign", snapshot.foreign_counts)):
            self.assertEqual(Counter(dict(counts)), Counter(e.path for e in starts if e.ownership == ownership), snapshot)
        self.assertEqual(Counter(dict(snapshot.counts)),
                         Counter(dict(snapshot.owned_counts)) + Counter(dict(snapshot.foreign_counts)), snapshot)

    def test_unique_identity_and_strict_partition_without_user_agent_or_path_rules(self):
        with BrowserFixture("same-case", "html") as first, BrowserFixture("same-case", "other") as other:
            self.assertNotEqual(first.request_headers, other.request_headers)
            before = first.snapshot()
            headers = {**first.request_headers, "User-Agent": "Go-http-client/1.1"}
            self.assertEqual(get(first, "/display", headers), (200, None, b"html"))
            self.assertEqual(get(first, "/", headers), (200, None, b"html"))
            for marker in ({}, {next(iter(first.request_headers)): "wrong"}, other.request_headers):
                self.assertEqual(get(first, "/", marker), (200, None, b"html"))
            snapshot = first.snapshot()
            self.assertEqual(snapshot.owned_counts, (("/", 1), ("/display", 1)), snapshot)
            self.assertGreaterEqual(dict(snapshot.foreign_counts)["/"], 3, snapshot)
            self.assert_partition(before)
            self.assertEqual(before.owned_counts, ())
            self.assert_partition(snapshot)
            self.assert_partition(other.snapshot())
            owned = [e for e in snapshot.events if e.kind == "handler.start" and e.ownership == "owned"]
            self.assertEqual([e.path for e in owned], ["/display", "/"])
            self.assertTrue(all(dict(e.headers)["User-Agent"] == "Go-http-client/1.1" for e in owned))
            for event in owned:
                with self.assertRaises((AttributeError, TypeError)):
                    event.ownership = "foreign"

    def test_independent_servers_and_late_handler_attribution(self):
        entered, release, done = Event(), Event(), Event()
        outcomes = []

        def gate(fixture, path):
            entered.set()
            if not release.wait(2):
                raise AssertionError("late-handler release timed out")

        with BrowserFixture("old-case", "old", before_response=gate) as old:
            def client():
                try:
                    outcomes.append(get(old))
                finally:
                    done.set()
            worker = Thread(target=client)
            worker.start()
            try:
                self.assertTrue(entered.wait(2))
                with BrowserFixture("new-case", "new") as new:
                    self.assertNotEqual(old.port, new.port)
                    self.assertNotEqual(old.generation, new.generation)
                    self.assertEqual(get(new), (200, None, b"new"))
                    new.html = "changed"
                    self.assertEqual(get(new), (200, None, b"changed"))
                    release.set()
                    self.assertTrue(done.wait(2))
                    self.assertEqual(outcomes, [(200, None, b"old")])
                    self.assertEqual(old.snapshot().owned_counts, (("/display", 1),), old.snapshot())
                    self.assertEqual(new.snapshot().owned_counts, (("/display", 2),), new.snapshot())
                    self.assert_partition(old.snapshot())
                    self.assert_partition(new.snapshot())
                    self.assertTrue(all(e.case == "old-case" for e in old.snapshot().events))
                    self.assertTrue(all(e.case == "new-case" for e in new.snapshot().events))
            finally:
                release.set()
                worker.join(2)
            self.assertFalse(worker.is_alive())
        self.assertTrue(old.snapshot().closed)
        self.assertEqual(old.snapshot().active_threads, 0)
        self.assertEqual(new.snapshot().active_threads, 0)

    def test_bounded_cleanup_on_exception_closes_every_owned_session(self):
        closed = []
        entered = Event()

        class Session:
            def __init__(self, label):
                self.label = label
            def close(self):
                closed.append(self.label)

        def gate(fixture, path):
            entered.set()
            if not fixture.stopping.wait(2):
                raise AssertionError("cleanup did not signal handler")

        fixture = BrowserFixture("cleanup", "body", before_response=gate)
        with self.assertRaisesRegex(ValueError, "assertion stand-in"):
            with fixture:
                fixture.own(Session("first"))
                fixture.own(Session("replacement"))
                # A partial HTTP header must not hold server_close forever.
                partial = HTTPConnection("127.0.0.1", fixture.port, timeout=2)
                partial.connect()
                self.addCleanup(partial.close)
                partial.sock.sendall(b"GET / HTTP/1.1\r\nHost: loopback\r\n")
                client_done = Event()
                def client():
                    try:
                        get(fixture)
                    except (OSError, TimeoutError):
                        pass  # shutdown may interrupt the response
                    finally:
                        client_done.set()
                worker = Thread(target=client)
                worker.start()
                self.assertTrue(entered.wait(2))
                raise ValueError("assertion stand-in")
        worker.join(2)
        self.assertTrue(client_done.is_set())
        self.assertFalse(worker.is_alive())
        self.assertEqual(closed, ["replacement", "first"])
        self.assertTrue(fixture.snapshot().closed)
        self.assertEqual(fixture.snapshot().active_threads, 0)
        self.assertEqual(fixture.snapshot().active_connections, 0)
        self.assertLess(fixture.cleanup_seconds, 2)
        fixture.close()
        self.assertEqual(closed, ["replacement", "first"])
        with self.assertRaises(OSError):
            get(fixture)

    def test_immutable_complete_provenance_and_unexpected_root_counts(self):
        with BrowserFixture("provenance", "html") as fixture:
            self.assertEqual(get(fixture, headers={**fixture.request_headers, "User-Agent": "looks-like-browser", "Sec-Fetch-Mode": "navigate"}), (200, None, b"html"))
            before = fixture.snapshot()
            self.assertEqual(get(fixture, "/"), (200, None, b"html"))
            self.assertEqual(get(fixture, "/disabled/display"), (302, "/", b""))
        after = fixture.snapshot()
        self.assertEqual(before.owned_counts, (("/display", 1),), before)
        self.assertEqual(dict(after.owned_counts), Counter({"/display": 1, "/": 1, "/disabled/display": 1}), after)
        self.assert_partition(before)
        self.assert_partition(after)
        starts = [e for e in after.events if e.kind == "handler.start" and e.ownership == "owned"]
        ends = [e for e in after.events if e.kind == "handler.end" and e.ownership == "owned"]
        self.assertEqual(len(starts), 3)
        self.assertEqual(len(ends), 3)
        self.assertEqual([e.request_id for e in starts], [e.request_id for e in ends])
        self.assertEqual([e.time for e in after.events], sorted(e.time for e in after.events))
        for event in starts + ends:
            self.assertEqual(event.case, "provenance")
            self.assertEqual(event.generation, fixture.generation)
            self.assertEqual(event.method, "GET")
            self.assertEqual(event.peer[0], "127.0.0.1")
            self.assertGreater(event.peer[1], 0)
            self.assertEqual(event.provenance, "socket peer only; client process unknown")
            self.assertTrue(dict(event.headers)["Host"].startswith("127.0.0.1:"))
        self.assertEqual(dict(starts[0].headers)["User-Agent"], "looks-like-browser")
        with self.assertRaises((AttributeError, TypeError)):
            starts[0].path = "hidden"
        self.assertIn("/disabled/display", repr(after))
        self.assertEqual(after.active_threads, 0)

    def test_scoped_page_route_correlation_and_restoration(self):
        class Request:
            method, url, headers = "GET", "http://127.0.0.1/display", {"User-Agent": "forwarded"}
        class Response:
            status, headers = 302, {"location": "/"}
        class Route:
            request = Request()
            def continue_(self, **kwargs):
                self.continue_options = kwargs
            def fallback(self, **kwargs):
                self.fallback_options = kwargs
            def fetch(self, **kwargs):
                self.options = kwargs
                return Response()
        class Owner:
            def __init__(self, page):
                self.page = page
                self.closed = False
            def close(self):
                if self.page.listeners:
                    raise AssertionError("listeners survived into owner teardown")
                self.closed = True

        class Page:
            def __init__(self):
                self.listeners = {}
                self.routes = []
                self.context = Owner(self)
                self.context.browser = Owner(self)
            def close(self):
                if self.listeners:
                    raise AssertionError("listeners survived into page teardown")
            def route(self, pattern, callback):
                self.routes.append((pattern, callback))
            def unroute(self, pattern, callback):
                self.routes.remove((pattern, callback))
            def on(self, event, callback):
                self.listeners[event] = callback
            def remove_listener(self, event, callback):
                self.listeners.pop(event)
            def goto(self, url, **kwargs):
                Request.frame = type("Frame", (), {"page": self})()
                self.listeners["request"](Request())
                response = route.fetch(max_redirects=0)
                self.listeners["response"](response)
                return response
        route, page = Route(), Page()
        original_goto, original_fetch, original_continue = Page.goto, Route.fetch, Route.continue_
        with BrowserFixture("trace", "html") as fixture:
            with self.assertRaisesRegex(ValueError, "exit"):
                with fixture.instrument(Page, Route):
                    self.assertEqual(page.goto(Request.url).status, 302)
                    page.routes[-1][1](route)
                    self.assertEqual(route.fallback_options["headers"], {**Request.headers, **fixture.request_headers})
                    route.continue_(headers={"X-Continue": "kept"}, method="POST")
                    self.assertEqual(route.continue_options, {"headers": {"X-Continue": "kept", **fixture.request_headers}, "method": "POST"})
                    original_headers = Request.headers
                    Request.headers = {**original_headers, "x-MarsDisplay-Test-Case": "other-case"}
                    page.routes[-1][1](route)
                    self.assertEqual(route.fallback_options, {"headers": Request.headers})
                    route.continue_(headers={"X-Continue": "kept", "X-MARSDISPLAY-TEST-CASE": "override"}, method="POST")
                    self.assertEqual(route.continue_options, {"headers": {"X-Continue": "kept", "X-MARSDISPLAY-TEST-CASE": "override"}, "method": "POST"})
                    Request.headers = original_headers
                    route.fetch(headers={"X-Custom": "kept", **fixture.request_headers, "x-marsdisplay-test-case": "explicit-other"}, method="POST", max_redirects=0)
                    self.assertEqual(route.options, {"headers": {"X-Custom": "kept", "x-marsdisplay-test-case": "explicit-other"}, "method": "POST", "max_redirects": 0})
                    # Later activity keeps the page's navigation correlation.
                    self.assertEqual(set(page.listeners), {"request", "response", "framenavigated"})
                    page.listeners["request"](Request())
                    # Detach BEFORE owner teardown, even inside the scope.
                    page.context.browser.close()
                    self.assertTrue(page.context.browser.closed)
                    self.assertEqual(page.listeners, {})
                    raise ValueError("exit")
            self.assertIs(Page.goto, original_goto)
            self.assertIs(Route.fetch, original_fetch)
            self.assertIs(Route.continue_, original_continue)
            self.assertEqual(page.listeners, {})
            self.assertEqual(page.routes, [])
            events = fixture.snapshot().events
            self.assertEqual([e.kind for e in events], ["page.goto.begin", "page.request", "route.fetch.begin", "route.fetch.end", "page.response", "page.goto.end", "route.fetch.begin", "route.fetch.end", "page.request"])
            self.assertEqual(len({e.navigation_id for e in events}), 1)
            self.assertIsNotNone(events[0].navigation_id)
            self.assertEqual(dict(events[3].details), {"status": 302, "location": "/"})
            self.assertEqual(events[2].headers, (("User-Agent", "forwarded"),))
            self.assertEqual(route.options, {"headers": {"X-Custom": "kept", "x-marsdisplay-test-case": "explicit-other"}, "method": "POST", "max_redirects": 0})
            self.assertTrue(all(e.provenance == "test API observation; not socket process identity" for e in events))
            self.assertEqual(fixture.snapshot().owned_counts, (), fixture.snapshot())
            self.assert_partition(fixture.snapshot())


if __name__ == "__main__":
    unittest.main()
