"""S5/T3a: one owned display page, including frontend-created popups."""
from collections import Counter
from pathlib import Path
from time import monotonic
import unittest
from unittest.mock import patch

from playwright.sync_api import Browser

from browser_fixture import BrowserFixture
from mars_display.browser import BrowserError, BrowserSession
from mars_display.settings import Settings


def query_gated_html(html, action):
    """Serve a deterministic SPA turn after the first root query, never patch routing."""
    return html.replace('</body>', '''<script>
        const queryAll = document.querySelectorAll.bind(document);
        document.querySelectorAll = selector => {
            const roots = queryAll(selector);
            if (selector === '#mars-display' && !window.fixtureRootQueried) {
                window.fixtureRootQueried = true;
                requestAnimationFrame(() => {''' + action + '''});
            }
            return roots;
        };
        </script></body>''')


class BrowserSecurityRegression(unittest.TestCase):
    def test_spa_mount_after_open_waits_for_first_frame_without_reopening(self):
        html = Path(__file__).with_name('fixtures').joinpath('display.html').read_text()
        html = html.replace('<div id="mars-display"', '<template id="bootstrap-root"><div id="mars-display"').replace('</div>', '</div></template>')
        html = query_gated_html(html, "document.body.append(document.getElementById('bootstrap-root').content);")
        contexts = []
        original = Browser.new_context
        with BrowserFixture(self.id(), html) as fixture:
            def recording(browser, *args, **kwargs):
                context = original(browser, *args, **kwargs)
                contexts.append(context)
                context.set_extra_http_headers(fixture.request_headers)
                return context

            with patch.object(Browser, 'new_context', recording):
                session = fixture.own(BrowserSession(Settings(fixture.url)))
                session.open()
                page = contexts[0].pages[0]
                self.assertTrue(page.evaluate("document.readyState !== 'loading' && document.getElementById('mars-display') === null && !window.fixtureRootQueried"))
                started = monotonic()
                first = session.read()
                session.open()  # Still the same owned page, not a recovery/reopen.
                second = session.read()
                for sample in (first, second):
                    self.assertEqual((sample.state, sample.live_connected, sample.data_stale), ('ready', True, False))
                    self.assertEqual((sample.frame.width, sample.frame.height), (320, 480))
                    self.assertEqual(sample.frame.rgb, bytes((17, 34, 51)) * (320 * 480))
                self.assertLessEqual(started, first.frame.captured_at)
                self.assertLessEqual(first.frame.captured_at, second.frame.captured_at)
                self.assertEqual(contexts[0].pages, [page])
                self.assertEqual(len(contexts), 1)
                session.close()
            snapshot = fixture.snapshot()
            self.assertEqual(dict(snapshot.owned_counts), {'/display': 1}, snapshot)
            self.assertEqual(Counter(dict(snapshot.counts)), Counter(dict(snapshot.owned_counts)) + Counter(dict(snapshot.foreign_counts)), snapshot)
            self.assertTrue(all(not context.pages for context in contexts))

    def test_path_change_during_absent_root_wait_rejects_even_loading_observation(self):
        html = Path(__file__).with_name('fixtures').joinpath('display.html').read_text()
        html = html.replace('state="ready"', 'state="loading"')
        html = html.replace('<div id="mars-display"', '<template id="bootstrap-root"><div id="mars-display"').replace('</div>', '</div></template>')
        html = query_gated_html(html, "history.pushState({}, '', '/left'); document.body.append(document.getElementById('bootstrap-root').content);")
        contexts = []
        original = Browser.new_context
        with BrowserFixture(self.id(), html) as fixture:
            def recording(browser, *args, **kwargs):
                context = original(browser, *args, **kwargs)
                contexts.append(context)
                context.set_extra_http_headers(fixture.request_headers)
                return context

            with patch.object(Browser, 'new_context', recording):
                session = fixture.own(BrowserSession(Settings(fixture.url)))
                session.open()
                self.assertTrue(contexts[0].pages[0].evaluate("document.getElementById('mars-display') === null && !window.fixtureRootQueried"))
                with self.assertRaises(BrowserError) as caught:
                    session.read()
                self.assertEqual(str(caught.exception), 'MARS left the configured display path; check direct display access.')
                self.assertEqual(len(contexts), 1)
                self.assertEqual(len(contexts[0].pages), 1)
                session.close()
            snapshot = fixture.snapshot()
            self.assertEqual(dict(snapshot.owned_counts), {'/display': 1}, snapshot)
            self.assertEqual(Counter(dict(snapshot.counts)), Counter(dict(snapshot.owned_counts)) + Counter(dict(snapshot.foreign_counts)), snapshot)
            self.assertTrue(all(not context.pages for context in contexts))

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
