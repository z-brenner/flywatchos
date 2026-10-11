"""Verify real host-controller fault traces; never opens firmware/device files."""
import json
import subprocess
import sys
import unittest


class FaultTraceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        result = subprocess.run([sys.argv[1]], check=True, capture_output=True,
                                text=True, timeout=10)
        cls.report = json.loads(result.stdout)
        cls.cases = {case['name']: case['steps'] for case in cls.report['scenarios']}

    def test_evidence_scope_and_determinism(self):
        self.assertEqual(self.report['schema'], 1)
        self.assertEqual(self.report['scope'], 'host-only proposed controller')
        self.assertFalse(self.report['target_modified'])
        self.assertFalse(self.report['hardware_verified'])
        self.assertEqual(len(self.cases), 6)
        repeat = subprocess.run([sys.argv[1]], check=True, capture_output=True,
                                text=True, timeout=10)
        self.assertEqual(json.loads(repeat.stdout), self.report)

    def test_rejection_is_not_completion(self):
        steps = self.cases['owned_button_queue_reject_then_display']
        self.assertEqual([s['op'] for s in steps],
                         ['owned_press', 'queue_reject', 'queue_accept', 'home_display'])
        self.assertEqual([s['attempts'] for s in steps], [0, 1, 2, 2])
        self.assertEqual([s['pending'] for s in steps], [True, True, True, False])
        self.assertEqual([s['acknowledged'] for s in steps], [False, False, False, True])
        self.assertFalse(steps[1]['enqueued'])
        self.assertTrue(steps[2]['enqueued'])

    def test_ineligible_key_never_posts(self):
        steps = self.cases['native_press_has_no_flyos_work']
        self.assertTrue(all(not s['pending'] and not s['attempted'] for s in steps))
        self.assertEqual(steps[0]['route'], 1)  # Garmin

    def test_new_input_invalidates_older_display(self):
        steps = self.cases['newer_input_invalidates_old_display']
        self.assertEqual([s['acknowledged'] for s in steps],
                         [False, False, False, False, False, True])
        self.assertEqual(steps[2]['attempts'], 1)
        self.assertGreater(steps[2]['epoch'], steps[1]['epoch'])
        self.assertTrue(steps[3]['pending'])

    def test_usb_and_modal_are_gates_not_queue_failures(self):
        steps = self.cases['usb_return_requires_eligible_callback']
        self.assertEqual([s['attempted'] for s in steps],
                         [False, False, False, False, True, False])
        self.assertEqual([s['attempts'] for s in steps], [0, 0, 0, 0, 1, 1])
        self.assertTrue(steps[-1]['acknowledged'])

    def test_failure_and_unacknowledged_acceptance_stay_unfinished(self):
        for name in ['permanent_rejection_is_bounded', 'acceptance_without_display_is_bounded']:
            steps = self.cases[name]
            self.assertEqual([s['attempts'] for s in steps], [0, 1, 2, 2, 2])
            self.assertTrue(steps[-1]['pending'])
            self.assertTrue(steps[-1]['exhausted'])
            self.assertFalse(steps[-1]['attempted'])
            self.assertTrue(all(not s['acknowledged'] for s in steps))
        self.assertTrue(self.cases['acceptance_without_display_is_bounded'][1]['enqueued'])
        self.assertFalse(self.cases['permanent_rejection_is_bounded'][1]['enqueued'])


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0]])
