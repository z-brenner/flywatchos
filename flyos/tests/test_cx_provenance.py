#!/usr/bin/env python3
"""Offline provenance, orientation, generated-table and attribution regressions."""
from collections import Counter
import csv
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'sim/data/pisokas2020'
GENERATOR = ROOT / 'tools/generate_cx_data.py'
SPEC = importlib.util.spec_from_file_location('cx_data_generator', GENERATOR)
GEN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GEN)

class Provenance(unittest.TestCase):
    def test_all_pinned_sources_and_generated_c_match(self):
        self.assertEqual(GEN.OUTPUT.read_text(), GEN.generated())

    def test_orientation_and_category_strengths(self):
        with (DATA / 'pisokas2020_cx60_edges.csv').open(newline='') as stream:
            rows = list(csv.DictReader(stream))
        edges = {(int(r['source']), int(r['target'])): r for r in rows}
        for source, target, label, weight in [
                (34, 0, '3.0', 99.9680554605268),
                (52, 0, '-1.0', -35.6772759590409),
                (7, 34, '1.0', 6.07203896674184),
                (35, 52, '1.1', 47.9173822984772),
                (53, 52, '-1.1', -19.3358579258735)]:
            self.assertEqual(edges[source, target]['category_label'], label)
            self.assertEqual(float(edges[source, target]['published_model_strength']), weight)
        self.assertEqual(Counter(r['category_label'] for r in rows),
                         {'-1.1': 56, '-1.0': 34, '1.0': 76, '1.1': 126, '3.0': 34})
        self.assertEqual(len(rows), 326)

    def test_metadata_matches_source_units_and_keeps_full_license(self):
        model = json.loads((ROOT / 'sim/circuit_models.json').read_text())['models'][1]
        nodes = json.loads((DATA / 'pisokas2020_cx60_nodes.json').read_text())
        self.assertEqual(model['license_notice'], (DATA / 'LICENSE').read_text())
        self.assertEqual(model['node_count'], 60)
        self.assertEqual(len(model['units']), 60)
        for unit, source in zip(model['units'], nodes):
            self.assertEqual(unit['id'], source['index'])
            self.assertEqual(unit['group'], source['class'])
            self.assertEqual(unit.get('cue_angle_degrees'), source.get('cue_angle_degrees'))
        self.assertIn('not the paper', ' '.join(model['approximations']).lower())
        self.assertEqual(model['gain'], 0.01)

    def test_tampered_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / 'data'
            shutil.copytree(DATA, folder)
            with (folder / 'pisokas2020_cx60_edges.csv').open('ab') as stream:
                stream.write(b'0,0,1.0,6.07203896674184\n')
            with mock.patch.object(GEN, 'DATA', folder):
                with self.assertRaises(AssertionError): GEN.generated()

    def test_stale_generated_table_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            stale = Path(temporary) / 'stale.inc'
            stale.write_text('stale data')
            with mock.patch.object(GEN, 'OUTPUT', stale), mock.patch.object(sys, 'argv', ['generator', '--check']):
                with self.assertRaisesRegex(AssertionError, 'stale'): GEN.main()

    def test_optimized_python_fails_closed_before_any_write(self):
        for script in (GENERATOR, DATA / 'export_pisokas.py'):
            result = subprocess.run([sys.executable, '-O', str(script)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('without -O/PYTHONOPTIMIZE', result.stderr)
            self.assertNotIn('verified', result.stdout)

    @unittest.skipUnless(importlib.util.find_spec('scipy'), 'optional independent MAT re-derivation requires SciPy')
    def test_original_mat_reproduces_every_exported_edge(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / 'data'
            shutil.copytree(DATA, folder)
            result = subprocess.run([sys.executable, str(folder / 'export_pisokas.py')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            for name in ('pisokas2020_cx60_edges.csv', 'pisokas2020_cx60_nodes.json',
                         'pisokas2020_cx60_provenance.json'):
                self.assertEqual((DATA / name).read_bytes(), (folder / name).read_bytes(), name)

    @unittest.skipUnless(importlib.util.find_spec('scipy'), 'optional MAT re-derivation requires SciPy')
    def test_json_rederivation_is_stable_with_windows_default_newlines(self):
        # Simulate Path.write_text's Windows default without requiring a
        # Windows runner. Explicit newline arguments must override the default.
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / 'data'
            shutil.copytree(DATA, folder)
            code = """
from pathlib import Path
import runpy, sys
original = Path.write_text
def windows_write_text(self, data, *args, **kwargs):
    kwargs.setdefault('newline', '\\r\\n')
    return original(self, data, *args, **kwargs)
Path.write_text = windows_write_text
runpy.run_path(sys.argv[1], run_name='__main__')
"""
            result = subprocess.run([sys.executable, '-c', code, str(folder / 'export_pisokas.py')],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            for name in ('pisokas2020_cx60_nodes.json', 'pisokas2020_cx60_provenance.json'):
                self.assertEqual((DATA / name).read_bytes(), (folder / name).read_bytes(), name)

if __name__ == '__main__': unittest.main()
