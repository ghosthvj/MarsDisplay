"""Test-only admitted child: every inventory/serial effect is fake and recorded."""
import json
from pathlib import Path
import sys
import time

from mars_display import linux_usb_worker as worker
from mars_display import usb_ipc as ipc
from mars_display.devices import USBSerialDescriptor


def main():
    mode, report, *args = sys.argv[1:]

    def record(kind, value=None):
        with Path(report).open('a', encoding='utf-8') as stream:
            stream.write(json.dumps([kind, value]) + '\n')

    def block(stage):
        if mode == stage:
            time.sleep(30)  # Parent deadline must kill/reap; bounded fixture watchdog.

    class Port:
        def open(self):
            record('open')
            block('open')

        def write(self, data):
            record('write', data.hex())
            block('write')
            return len(data)

        @property
        def out_waiting(self):
            record('drain')
            block('drain')
            return 0

        def close(self):
            record('close')
            block('close')

    def inventory():
        record('inventory')
        return (USBSerialDescriptor('/dev/ttyACM0', 0x1a86, 0x5722,
                'USB35INCHIPSV2', None, None, None, None, None),)

    def factory(**options):
        record('options', options)
        return Port()

    if mode == 'nonce':
        def wrong_nonce(channel, nonce, **options):
            ipc.send_packet(channel, ipc.HELLO, 0, b'x' * 32, time.monotonic() + 2)
            time.sleep(30)
        worker.run_session = wrong_nonce
    return worker.main(args, inventory=inventory, port_factory=factory)


if __name__ == '__main__':
    raise SystemExit(main())
