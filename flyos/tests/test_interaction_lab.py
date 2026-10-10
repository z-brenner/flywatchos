"""Exercise the real C trace exporter and the standalone offline lab artifact."""
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

EXPORTER = Path(sys.argv.pop(1)).resolve() if len(sys.argv) > 1 else None
BUILDER = Path(__file__).parents[1] / 'tools' / 'build_interaction_lab.py'
EXPECTED = {'home-controls', 'native-escape', 'view-transition', 'usb-detach',
            'retry-exhaustion', 'stale-ack', 'invalid-view'}

class InteractionLabTests(unittest.TestCase):
    def export(self):
        self.assertTrue(EXPORTER and EXPORTER.is_file(), 'C interaction exporter has not been built')
        result = subprocess.run([str(EXPORTER)], capture_output=True, check=True)
        return result.stdout, json.loads(result.stdout)

    def test_exports_deterministic_real_renderer_traces(self):
        raw, data = self.export()
        self.assertEqual(raw, self.export()[0])
        self.assertEqual(data['schema'], 1)
        self.assertEqual(data['scope'], 'host-only')
        self.assertFalse(data['hardware_verified'])
        self.assertEqual({s['id'] for s in data['scenarios']}, EXPECTED)
        for scenario in data['scenarios']:
            self.assertGreaterEqual(len(scenario['frames']), 3)
            for frame in scenario['frames']:
                self.assertEqual(len(frame['neurons']), 64)
                self.assertTrue(all(-16384 <= n <= 16383 for n in frame['neurons']))
                runs = frame['pixels']
                self.assertEqual(sum(n for _, n in runs), 240 * 240)
                self.assertTrue(all(role in range(6) and count > 0 for role, count in runs))
                self.assertIn(frame['view'], ['HOME', 'NON_HOME', 'INVALID'])
                self.assertIn(frame['route'], ['NONE', 'FLYOS', 'GARMIN', 'REJECTED'])
        by_id = {s['id']: s['frames'] for s in data['scenarios']}
        home = by_id['home-controls']
        self.assertGreater(home[1]['neurons'][1], home[0]['neurons'][1])
        self.assertEqual(home[1]['route'], 'FLYOS')
        self.assertEqual(home[2]['route'], 'FLYOS')
        self.assertEqual(home[2]['pulse_mask'], 2)
        # Actual framebuffer changed after the real brain response.
        self.assertNotEqual(home[0]['pixels'], home[1]['pixels'])
        self.assertEqual(by_id['view-transition'][2]['route'], 'FLYOS')
        self.assertEqual(by_id['view-transition'][2]['view'], 'NON_HOME')
        transition = by_id['view-transition']
        waiting = [f for f in transition if f['view'] != 'HOME' and f['pulse_mask']]
        self.assertGreaterEqual(len(waiting), 2)
        self.assertTrue(all(f['input_buttons'] == 0 for f in waiting))
        self.assertEqual(transition[-2]['input_buttons'], 2)
        self.assertEqual(transition[-1]['input_buttons'], 0)
        self.assertEqual(by_id['native-escape'][1]['route'], 'GARMIN')
        self.assertEqual(by_id['invalid-view'][1]['route'], 'GARMIN')
        self.assertTrue(by_id['usb-detach'][-1]['redraw_complete'])
        self.assertTrue(by_id['retry-exhaustion'][-1]['redraw_exhausted'])
        self.assertFalse(by_id['retry-exhaustion'][-1]['redraw_complete'])
        self.assertFalse(by_id['stale-ack'][-1]['redraw_complete'])

    def test_exporter_rejects_unrecognized_arguments(self):
        self.assertTrue(EXPORTER and EXPORTER.is_file(), 'C interaction exporter has not been built')
        result = subprocess.run([str(EXPORTER), '--write-firmware'], capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b'')

    def test_standalone_bundle_and_hash_manifest(self):
        self.assertTrue(BUILDER.is_file(), 'offline lab builder is not implemented')
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'lab'
            args = [sys.executable, str(BUILDER), '--exporter', str(EXPORTER), '--output', str(output)]
            subprocess.run(args, check=True, capture_output=True)
            html = (output / 'index.html').read_text()
            self.assertIn('FlyWatch / Interaction Lab', html)
            self.assertIn('id="lab-data"', html)
            self.assertNotIn('src="http', html)
            self.assertNotIn('href="http', html)
            payload = html.split('<script id="lab-data" type="application/json">', 1)[1].split('</script>', 1)[0]
            data = json.loads(payload)
            self.assertEqual({s['id'] for s in data['scenarios']}, EXPECTED)
            for s in data['scenarios']:
                for frame in s['frames']:
                    png = base64.b64decode(frame['image'].split(',', 1)[1], validate=True)
                    self.assertTrue(png.startswith(b'\x89PNG\r\n\x1a\n'))
            for line in (output / 'SHA256SUMS').read_text().splitlines():
                digest, filename = line.split('  ', 1)
                self.assertEqual(digest, hashlib.sha256((output / filename).read_bytes()).hexdigest())
            first = (output / 'index.html').read_bytes()
            # Existing captures must not be silently overwritten.
            repeat = subprocess.run(args, capture_output=True)
            self.assertNotEqual(repeat.returncode, 0)
            self.assertEqual(first, (output / 'index.html').read_bytes())

if __name__ == '__main__':
    unittest.main()
