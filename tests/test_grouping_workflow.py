"""Static trigger contract; actual event admission is verified by GitHub CI."""
from pathlib import Path
import unittest


class GroupingWorkflowTests(unittest.TestCase):
    def test_push_is_limited_to_experiment_branch_and_paths(self):
        workflow = (Path(__file__).parents[1] / '.github/workflows/windows-usb-grouping.yml').read_text()
        triggers = workflow.split('\non:\n', 1)[1].split('\npermissions:', 1)[0]
        self.assertEqual(triggers, """  workflow_dispatch:
  push:
    branches: [feat/native-usb-hardware]
    paths:
      - '.github/workflows/windows-usb-grouping.yml'
      - 'src/mars_display/usb_grouping_*.py'
      - 'packaging/build_grouping_experiment.py'
      - 'packaging/grouping_*.py'
      - 'packaging/MarsDisplayGroupingExperiment.spec'
      - 'packaging/GROUPING-README.txt'
      - 'tests/test_grouping_*.py'
      - 'tests/test_usb_grouping_*.py'
      - 'docs/usb-grouping-*.md'""")

    def test_manual_route_and_delivery_guards_remain(self):
        workflow = (Path(__file__).parents[1] / '.github/workflows/windows-usb-grouping.yml').read_text()
        self.assertIn('  workflow_dispatch:\n', workflow)
        self.assertIn('permissions:\n  contents: read\n', workflow)
        self.assertIn('r.wasSuccessful() and not r.skipped', workflow)
        self.assertIn('if: ${{ success() }}', workflow)
        self.assertNotIn('pull_request:', workflow)
        self.assertNotIn('schedule:', workflow)
