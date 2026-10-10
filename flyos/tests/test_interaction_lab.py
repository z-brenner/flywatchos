"""Exercise the real C trace exporter and the standalone offline lab artifact."""
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

EXPORTER = Path(sys.argv.pop(1)).resolve() if len(sys.argv) > 1 else None
BUILDER = Path(__file__).parents[1] / 'tools' / 'build_interaction_lab.py'
EXPECTED = {'home-controls', 'native-escape', 'view-transition', 'usb-detach',
            'retry-exhaustion', 'stale-ack', 'invalid-view',
            'classifier-guards', 'classifier-stability'}

spec = importlib.util.spec_from_file_location('lab_builder', BUILDER)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)

class InteractionLabTests(unittest.TestCase):
    def test_model_metadata_rejects_unsafe_or_ambiguous_schema(self):
        model = dict(id=0, key='baseline', label='Abstract baseline',
                     description='A hand-authored model.', biological_basis='None.',
                     approximations=['Not a connectome.'], scale=1024,
                     units=[dict(id=0, label='N00', group='Input', role='sensory')],
                     sources=[])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'models.json'
            def check(value):
                path.write_text(json.dumps(value))
                return builder.load_model_metadata(path)
            self.assertEqual(check({'models': [model]}), [model])
            invalid = [
                {'models': [model, model]},
                {'models': [{**model, 'scale': 0}]},
                {'models': [{**model, 'id': True}]},
                {'models': [{**model, 'units': []}]},
                {'models': [{**model, 'units': [dict(id=1, label='N01', group='X')]}]},
                {'models': [{**model, 'sources': [dict(title='Unsafe', url='javascript:alert(1)')]}]},
                {'models': [{**model, 'approximations': 'Not an array'}]},
            ]
            for value in invalid:
                with self.subTest(value=value), self.assertRaises(ValueError):
                    check(value)

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

    def test_classifier_scenarios_route_uncertainty_safely(self):
        _, data = self.export()
        by_id = {scenario['id']: scenario['frames'] for scenario in data['scenarios']}
        self.assertIn('classifier-guards', list(by_id), 'bounded classifier replay is not implemented')
        self.assertIn('classifier-stability', list(by_id))
        guards = {f['action']: f for f in by_id['classifier-guards']}
        for action in ['Unaligned pointer', 'Out-of-range node', 'Broken backlink',
                       'Cycle detected', 'Ninth node rejected', 'Unreadable field',
                       'All nodes hidden']:
            frame = guards[action]
            self.assertEqual(frame['view'], 'INVALID', action)
            self.assertEqual(frame['route'], 'GARMIN', action)
            self.assertEqual(frame['input_buttons'], 0, action)
            self.assertEqual(frame['attempts'], 0, action)
            self.assertTrue(frame['redraw_pending'], action)
            self.assertFalse(frame['enqueued'], action)
            self.assertEqual(frame['classifier']['source'], 'synthetic-reader')
            self.assertGreater(frame['classifier']['reads'], 0)
            self.assertLessEqual(frame['classifier']['reads'], 68)
        self.assertEqual(guards['Hidden HOME, visible native']['view'], 'NON_HOME')
        self.assertEqual(guards['Eight valid nodes']['view'], 'HOME')
        self.assertEqual(guards['Eight valid nodes']['classifier']['reads'], 68)
        self.assertEqual(guards['Eight valid nodes']['route'], 'FLYOS')
        self.assertTrue(guards['Eight valid nodes']['enqueued'])
        stability = {f['action']: f for f in by_id['classifier-stability']}
        for action in ['Identity changed between captures', 'Root changed during capture']:
            self.assertEqual(stability[action]['view'], 'INVALID')
            self.assertEqual(stability[action]['route'], 'GARMIN')
        # Explicit counterexample: two equal snapshots cannot detect complete ABA.
        aba = stability['Complete ABA is invisible']
        self.assertEqual(aba['view'], 'HOME')
        self.assertEqual(aba['classifier']['limitation'], 'complete-ABA')
        self.assertIn('not atomic', aba['detail'])
        self.assertFalse(data['hardware_verified'])

    def test_exporter_rejects_unrecognized_arguments(self):
        self.assertTrue(EXPORTER and EXPORTER.is_file(), 'C interaction exporter has not been built')
        result = subprocess.run([str(EXPORTER), '--write-firmware'], capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b'')

    def test_builder_embeds_optional_wasm_without_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wasm = root / 'empty.wasm'
            wasm.write_bytes(b'\x00asm\x01\x00\x00\x00')
            output = root / 'lab'
            result = subprocess.run([sys.executable, str(BUILDER), '--exporter', str(EXPORTER),
                                     '--output', str(output), '--wasm', str(wasm)], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            html = (output / 'index.html').read_text()
            payload = html.split('<script id="lab-data" type="application/json">', 1)[1].split('</script>', 1)[0]
            data = json.loads(payload)
            self.assertEqual(base64.b64decode(data['live_wasm']), wasm.read_bytes())
            self.assertEqual(data['live_wasm_sha256'], hashlib.sha256(wasm.read_bytes()).hexdigest())
            self.assertIn("'wasm-unsafe-eval'", html)
            self.assertNotIn('fetch(', html)

    def test_builder_rejects_malformed_wasm(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wasm = root / 'invalid.wasm'
            wasm.write_bytes(b'not a WebAssembly module')
            result = subprocess.run([sys.executable, str(BUILDER), '--exporter', str(EXPORTER),
                                     '--output', str(root / 'lab'), '--wasm', str(wasm)], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('invalid WebAssembly', result.stderr.decode())
            self.assertFalse((root / 'lab' / 'index.html').exists())

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
