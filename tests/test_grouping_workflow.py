"""Static trigger contract; actual event admission is verified by GitHub CI."""
from pathlib import Path
import unittest


class GroupingWorkflowTests(unittest.TestCase):
    def test_only_manual_dispatch_remains(self):
        workflow = (Path(__file__).parents[1] / '.github/workflows/windows-usb-grouping.yml').read_text()
        triggers = workflow.split('\non:\n', 1)[1].split('\npermissions:', 1)[0]
        self.assertEqual(triggers, '  workflow_dispatch:')

    def test_manual_route_and_delivery_guards_remain(self):
        workflow = (Path(__file__).parents[1] / '.github/workflows/windows-usb-grouping.yml').read_text()
        self.assertIn('  workflow_dispatch:\n', workflow)
        self.assertIn('permissions:\n  contents: read\n', workflow)
        self.assertIn('r.wasSuccessful() and not r.skipped', workflow)
        self.assertIn('if: ${{ success() }}', workflow)
        self.assertNotIn('pull_request:', workflow)
        self.assertNotIn('schedule:', workflow)
