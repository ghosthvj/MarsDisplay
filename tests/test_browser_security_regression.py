"""S5/T3a: one owned display page, including frontend-created popups."""
from pathlib import Path
import unittest
from unittest.mock import patch

from playwright.sync_api import Browser

from browser_fixture import BrowserFixture
from mars_display.browser import BrowserError, BrowserSession
from mars_display.settings import Settings


class BrowserSecurityRegression(unittest.TestCase):
    def test_display_cannot_open_a_second_display_client(self):
        html = Path(__file__).with_name("fixtures").joinpath("display.html").read_text()
        html = html.replace(
            "</body>",
            "<script>if (!window.opener) window.open('/display');</script></body>",
        )
        contexts = []
        original = Browser.new_context
        with BrowserFixture(self.id(), html) as fixture:
            def recording(browser, *args, **kwargs):
                context = original(browser, *args, **kwargs)
                contexts.append(context)
                context.set_extra_http_headers(fixture.request_headers)
                return context

            # Trace instrumentation changes popup routing. Exercise the actual
            # source boundary instead, tagging only the test context's traffic.
            with patch.object(Browser, "new_context", recording):
                session = fixture.own(BrowserSession(Settings(fixture.url)))
                try:
                    session.open()
                    session.read()
                except BrowserError:
                    pass  # Rejecting the attempted second client is fail-closed.
                pages = [page.url for context in contexts for page in context.pages]
                session.close()
            snapshot = fixture.snapshot()
            self.assertEqual(dict(snapshot.owned_counts), {"/display": 1}, snapshot)
            self.assertLessEqual(len(pages), 1, pages)
            self.assertTrue(all(not context.pages for context in contexts))


if __name__ == "__main__":
    unittest.main(verbosity=2)
