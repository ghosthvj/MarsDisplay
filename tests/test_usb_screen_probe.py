"""Offline public-page tests; serial is always synthetic, never hardware."""
import json
from pathlib import Path
import unittest

from playwright.sync_api import expect, sync_playwright

HTML = Path(__file__).resolve().parents[1] / "tools/usb-screen-probe.html"

MOCK = r"""
const mode = MODE;
window.calls = {choose: [], open: [], writes: [], close: 0};
window.transport = {events: [], pending: [], delivered: [], discarded: [], lockedAtClose: []};
const nativeTimeout = window.setTimeout.bind(window);
if (mode.includes('timeout') || mode === 'late-open') {
  window.setTimeout = (fn, ms) => nativeTimeout(fn, Math.min(ms, 20));
}
const port = {
  getInfo: () => ({usbVendorId: mode === 'wrong' ? 1 : 0x1a86, usbProductId: 0x5722}),
  open: async options => {
    calls.open.push(options);
    if (mode === 'busy') throw new Error('busy');
    if (mode === 'open-timeout') await new Promise(() => {});
    if (mode === 'late-open') await new Promise(r => nativeTimeout(r, 80));
  },
  writable: new WritableStream({write(bytes) {
    calls.writes.push(Array.from(bytes));
    transport.events.push('write');
    transport.pending.push(...bytes);
    if (mode === 'reject') return Promise.reject(new Error('write failed'));
    if (mode === 'write-timeout') return new Promise(() => {});
  }, async close() {
    transport.events.push('stream-close');
    document.documentElement.dataset.draining = 'true';
    if (mode === 'drain-reject') throw new Error('drain failed');
    if (mode === 'drain-timeout') await new Promise(() => {});
    if (mode === 'drain-pending') await new Promise(resolve => { window.resolveDrain = resolve; });
    transport.delivered = transport.pending;
    transport.pending = [];
    transport.events.push('drained');
  }}),
  close: async () => {
    calls.close++;
    transport.events.push('port-close');
    transport.lockedAtClose.push(port.writable.locked);
    transport.discarded = transport.pending;
    transport.pending = [];
    document.documentElement.dataset.closed = String(calls.close);
    if (port.writable.locked) throw new Error('writer still locked');
    if (mode === 'close-timeout') await new Promise(() => {});
  }
};
Object.defineProperty(navigator, 'serial', {value: mode === 'unsupported' ? undefined : {
  requestPort: async options => {
    calls.choose.push(options);
    if (mode === 'cancel') throw new DOMException('cancel', 'NotFoundError');
    return port;
  },
  getPorts: () => {throw new Error('must not enumerate');}
}});
if (mode === 'insecure') Object.defineProperty(window, 'isSecureContext', {value: false});
"""


class USBScreenProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not HTML.is_file():
            raise AssertionError(f"Missing probe HTML: {HTML}")
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def page(self, mode='ok'):
        context = self.browser.new_context()
        self.addCleanup(context.close)
        page = context.new_page()
        errors, requests = [], []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('console', lambda message: errors.append(message.text) if message.type == 'error' else None)
        page.on('request', lambda request: requests.append(request.url) if not request.url.startswith('file:') else None)
        self.addCleanup(lambda: self.assertEqual(errors, []))
        self.addCleanup(lambda: self.assertEqual(requests, []))
        page.add_init_script(MOCK.replace('MODE', json.dumps(mode)))
        page.goto(HTML.as_uri())
        return page

    def send(self, page):
        page.locator('#confirm').check()
        page.locator('#send').click()
        # Also attempt a second event while the operation owns the latch.
        page.locator('#send').dispatch_event('click')
        expect(page.locator('#status')).to_have_attribute('data-done', 'true')

    def test_idle_and_unsupported_preview(self):
        for mode in ('ok', 'unsupported', 'insecure'):
            with self.subTest(mode=mode):
                page = self.page(mode)
                self.assertTrue(page.locator('#send').is_disabled())
                self.assertEqual(page.evaluate('calls'), {'choose': [], 'open': [], 'writes': [], 'close': 0})
                self.assertEqual(page.locator('canvas').evaluate('(c) => [c.width,c.height]'), [320, 480])
                pixels = page.locator('canvas').evaluate('(c) => Array.from(c.getContext("2d").getImageData(0,0,320,480).data)')
                colors = set(zip(pixels[0::4], pixels[1::4], pixels[2::4]))
                self.assertTrue({(255,0,0), (0,255,0), (0,0,255), (255,255,255), (0,0,0)} <= colors)
                page.locator('#confirm').check()
                self.assertEqual(page.locator('#send').is_disabled(), mode != 'ok')
                if mode != 'ok':
                    self.assertIn('No send', page.locator('#status').inner_text())

    def test_exact_preview_wire_and_one_shot(self):
        page = self.page()
        rgba = page.locator('canvas').evaluate('(c) => Array.from(c.getContext("2d").getImageData(0,0,320,480).data)')
        self.send(page)
        calls = page.evaluate('calls')
        self.assertEqual(calls['choose'], [{'filters': [{'usbVendorId': 0x1a86, 'usbProductId': 0x5722}]}])
        self.assertEqual(calls['open'], [{'baudRate': 115200, 'dataBits': 8, 'stopBits': 1, 'parity': 'none', 'flowControl': 'hardware'}])
        self.assertEqual(calls['writes'][0], [0,0,0,0,0,121,100,1,64,1,224,0,0,0,0,0])
        self.assertEqual(calls['writes'][1], [0,0,4,253,223,197])
        self.assertEqual([len(chunk) for chunk in calls['writes'][2:]], [2560] * 120)
        expected = bytearray()
        for r, g, b in zip(rgba[0::4], rgba[1::4], rgba[2::4]):
            value = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
            expected.extend((value & 255, value >> 8))
        self.assertEqual(bytes(v for chunk in calls['writes'][2:] for v in chunk), bytes(expected))
        self.assertEqual(calls['close'], 1)
        self.assertEqual(page.locator('#status').inner_text(), '307222 bytes drained to the serial output; not a rendering ACK. Photograph the screen. Reload only after checking the device.')
        page.locator('#send').dispatch_event('click')
        self.assertEqual(page.evaluate('calls'), calls)
        page.reload()
        self.assertEqual(page.evaluate('calls.choose'), [])
        self.assertTrue(page.locator('#send').is_disabled())

    def test_stream_drain_precedes_unlocked_port_close(self):
        page = self.page()
        self.send(page)
        transport = page.evaluate('transport')
        self.assertEqual(transport['events'], ['write'] * 122 + ['stream-close', 'drained', 'port-close'])
        self.assertEqual(transport['lockedAtClose'], [False])
        self.assertEqual(transport['delivered'], page.evaluate('calls.writes.flat()'))
        self.assertEqual(len(transport['delivered']), 307222)
        self.assertEqual(transport['pending'], [])
        self.assertEqual(transport['discarded'], [])

    def test_pending_drain_has_no_success_or_port_close(self):
        page = self.page('drain-pending')
        page.locator('#confirm').check()
        page.locator('#send').click()
        expect(page.locator('html')).to_have_attribute('data-draining', 'true')
        self.assertEqual(page.locator('#status').inner_text(), 'Draining serial output. Do not disconnect during the transfer.')
        self.assertIsNone(page.locator('#status').get_attribute('data-done'))
        self.assertTrue(page.locator('#send').is_disabled())
        self.assertTrue(page.locator('#confirm').is_disabled())
        calls = page.evaluate('calls')
        self.assertEqual(len(calls['writes']), 122)
        self.assertEqual(calls['close'], 0)
        self.assertEqual(page.evaluate('transport.delivered'), [])
        self.assertEqual(page.evaluate('transport.pending.length'), 307222)
        page.locator('#send').dispatch_event('click')
        self.assertEqual(page.evaluate('calls'), calls)
        page.evaluate('resolveDrain()')
        expect(page.locator('#status')).to_have_attribute('data-done', 'true')
        self.assertEqual(page.locator('#status').inner_text(), '307222 bytes drained to the serial output; not a rendering ACK. Photograph the screen. Reload only after checking the device.')
        self.assertEqual(page.evaluate('transport.events'), ['write'] * 122 + ['stream-close', 'drained', 'port-close'])
        self.assertEqual(page.evaluate('transport.lockedAtClose'), [False])
        self.assertEqual(page.evaluate('transport.delivered.length'), 307222)
        self.assertEqual(page.evaluate('transport.discarded'), [])

    def test_drain_rejection_and_timeout_are_uncertain_one_shot(self):
        for mode in ('drain-reject', 'drain-timeout'):
            with self.subTest(mode=mode):
                page = self.page(mode)
                self.send(page)
                self.assertEqual(page.locator('#status').inner_text(), 'Drain failed or timed out; delivery uncertain, possible partial image. Disconnect/reconnect before retrying. Reload only after checking the device.')
                transport = page.evaluate('transport')
                self.assertEqual(transport['events'], ['write'] * 122 + ['stream-close', 'port-close'])
                self.assertEqual(transport['lockedAtClose'], [False])
                self.assertEqual(transport['delivered'], [])
                self.assertEqual(transport['pending'], [])
                self.assertEqual(len(transport['discarded']), 307222)
                calls = page.evaluate('calls')
                self.assertEqual(transport['discarded'], [v for chunk in calls['writes'] for v in chunk])
                self.assertEqual(calls['close'], 1)
                self.assertTrue(page.locator('#send').is_disabled())
                self.assertTrue(page.locator('#confirm').is_disabled())
                page.locator('#send').dispatch_event('click')
                self.assertEqual(page.evaluate('calls'), calls)

    def test_failures_and_bounded_cleanup(self):
        cases = {
            'cancel': (0, 0, 0, 'Selection cancelled'),
            'wrong': (0, 0, 0, 'Wrong VID/PID'),
            'busy': (1, 0, 1, 'Open failed'),
            'reject': (1, 1, 1, 'Transfer failed'),
            'write-timeout': (1, 1, 1, 'Transfer failed'),
            'open-timeout': (1, 0, 0, 'Cleanup uncertain'),
            'late-open': (1, 0, 1, 'Cleanup uncertain'),
            'close-timeout': (1, 122, 1, 'Cleanup uncertain'),
        }
        for mode, (opens, writes, closes, message) in cases.items():
            with self.subTest(mode=mode):
                page = self.page(mode)
                self.send(page)
                if mode == 'late-open':
                    expect(page.locator('html')).to_have_attribute('data-closed', '1')
                calls = page.evaluate('calls')
                self.assertEqual(len(calls['choose']), 1)
                self.assertEqual((len(calls['open']), len(calls['writes']), calls['close']), (opens, writes, closes))
                self.assertIn(message, page.locator('#status').inner_text())
                if writes:
                    self.assertIn('partial', page.locator('#status').inner_text())
                self.assertTrue(page.locator('#send').is_disabled())
                page.locator('#send').dispatch_event('click')
                self.assertEqual(page.evaluate('calls'), calls)


if __name__ == '__main__':
    unittest.main()
