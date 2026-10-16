"""Standard-library fixture proofs; no browser, Qt or application imports."""
from collections import Counter
from http.client import HTTPConnection
from threading import Event, Thread
import unittest

from browser_fixture import BrowserFixture


def get(fixture, path="/display", headers=None):
    connection = HTTPConnection("127.0.0.1", fixture.port, timeout=2)
    try:
        connection.request("GET", path, headers=headers or {})
        response = connection.getresponse()
        return response.status, response.getheader("Location"), response.read()
    finally:
        connection.close()


class FixtureTests(unittest.TestCase):
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
                    self.assertEqual(old.snapshot().counts, (("/display", 1),))
                    self.assertEqual(new.snapshot().counts, (("/display", 2),))
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
            self.assertEqual(get(fixture, headers={"User-Agent": "looks-like-browser", "Sec-Fetch-Mode": "navigate"}), (200, None, b"html"))
            before = fixture.snapshot()
            self.assertEqual(get(fixture, "/"), (200, None, b"html"))
            self.assertEqual(get(fixture, "/disabled/display"), (302, "/", b""))
        after = fixture.snapshot()
        self.assertEqual(before.counts, (("/display", 1),))
        self.assertEqual(dict(after.counts), Counter({"/display": 1, "/": 1, "/disabled/display": 1}))
        starts = [e for e in after.events if e.kind == "handler.start"]
        ends = [e for e in after.events if e.kind == "handler.end"]
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
                self.context = Owner(self)
                self.context.browser = Owner(self)
            def close(self):
                if self.listeners:
                    raise AssertionError("listeners survived into page teardown")
            def on(self, event, callback):
                self.listeners[event] = callback
            def remove_listener(self, event, callback):
                self.listeners.pop(event)
            def goto(self, url, **kwargs):
                self.listeners["request"](Request())
                response = route.fetch(max_redirects=0)
                self.listeners["response"](response)
                return response
        route, page = Route(), Page()
        original_goto, original_fetch = Page.goto, Route.fetch
        with BrowserFixture("trace", "html") as fixture:
            with self.assertRaisesRegex(ValueError, "exit"):
                with fixture.instrument(Page, Route):
                    self.assertEqual(page.goto(Request.url).status, 302)
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
            self.assertEqual(page.listeners, {})
            events = fixture.snapshot().events
            self.assertEqual([e.kind for e in events], ["page.goto.begin", "page.request", "route.fetch.begin", "route.fetch.end", "page.response", "page.goto.end", "page.request"])
            self.assertEqual(len({e.navigation_id for e in events}), 1)
            self.assertIsNotNone(events[0].navigation_id)
            self.assertEqual(dict(events[3].details), {"status": 302, "location": "/"})
            self.assertEqual(events[2].headers, (("User-Agent", "forwarded"),))
            self.assertEqual(route.options, {"max_redirects": 0})
            self.assertTrue(all(e.provenance == "test API observation; not socket process identity" for e in events))
            self.assertEqual(fixture.snapshot().counts, ())


if __name__ == "__main__":
    unittest.main()
