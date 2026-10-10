#!/usr/bin/env python3
"""Offline exact-source, projection, schema and reproducibility regressions."""
from collections import Counter
import copy
import csv
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'sim/data/hulse2021'
GENERATOR = ROOT / 'tools/generate_hulse_data.py'


class HulseProvenance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gen = None
        if GENERATOR.exists():
            spec = importlib.util.spec_from_file_location('hulse_generator', GENERATOR)
            cls.gen = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cls.gen)

    def generator(self):
        self.assertIsNotNone(self.gen, 'Measured-anatomy extractor is required')
        return self.gen

    def test_checked_in_outputs_are_exactly_rederived(self):
        gen = self.generator()
        outputs = gen.generated(DATA)
        self.assertEqual(set(outputs), {gen.ANATOMY_NAME, gen.PROVENANCE_NAME,
                                       gen.NODES_NAME, gen.EDGES_NAME})
        for name, expected in outputs.items():
            self.assertEqual((DATA / name).read_bytes(), expected, name)

    def test_raw_bytes_match_pinned_github_blobs_and_sha256(self):
        gen = self.generator()
        for name, record in gen.SOURCES.items():
            contents = gzip.decompress((DATA / (name + '.gz')).read_bytes())
            self.assertEqual(len(contents), record['bytes'])
            self.assertEqual(hashlib.sha256(contents).hexdigest(), record['sha256'])
            blob = b'blob ' + str(len(contents)).encode('ascii') + b'\0' + contents
            self.assertEqual(hashlib.sha1(blob).hexdigest(), record['git_blob_sha1'])

    def test_all_cells_edges_and_direction_totals(self):
        gen = self.generator()
        anatomy = json.loads(gen.generated(DATA)[gen.ANATOMY_NAME])
        nodes, links = anatomy['nodes'], anatomy['links']
        self.assertEqual(len(nodes), 56)
        self.assertEqual(Counter(n['class'] for n in nodes), {'EPG': 46, 'ER4m': 10})
        self.assertTrue(all(type(n['body_id']) is str for n in nodes))
        self.assertTrue(any(int(n['body_id']) > 2**32 for n in nodes))
        self.assertEqual(len(links), 762)
        self.assertEqual(sum(e['count'] for e in links), 16774)
        self.assertEqual(Counter((nodes[e['source']]['class'], nodes[e['target']]['class'])
                                 for e in links), {('ER4m', 'EPG'): 460, ('EPG', 'ER4m'): 302})
        for source, target, expected in [('ER4m', 'EPG', 14903), ('EPG', 'ER4m', 1871)]:
            self.assertEqual(sum(e['count'] for e in links if
                                 nodes[e['source']]['class'] == source and
                                 nodes[e['target']]['class'] == target), expected)

    def test_orientation_sentinels(self):
        gen = self.generator()
        anatomy = json.loads(gen.generated(DATA)[gen.ANATOMY_NAME])
        nodes = anatomy['nodes']
        edges = {(nodes[e['source']]['body_id'], nodes[e['target']]['body_id']): e['count']
                 for e in anatomy['links']}
        self.assertEqual(edges['1198326456', '449438847'], 57)
        self.assertEqual(edges['387364605', '1167977970'], 13)
        self.assertEqual(edges['1292847181', '449438847'], 52)
        self.assertEqual(edges['449438847', '1292847181'], 4)

    def test_every_selected_raw_row_is_preserved_without_filling_missing_pairs(self):
        gen = self.generator()
        expected = {}
        for name in gen.SOURCES:
            with gzip.open(DATA / (name + '.gz'), 'rt', newline='', encoding='utf-8') as stream:
                for row in csv.DictReader(stream):
                    if {row['databaseType.from'], row['databaseType.to']} == {'ER4m', 'EPG'}:
                        self.assertEqual(row['roi'], 'EB')
                        pair = (row['from'], row['to'])
                        self.assertNotIn(pair, expected)
                        expected[pair] = int(row['ROIweight'])
        anatomy = json.loads(gen.generated(DATA)[gen.ANATOMY_NAME])
        nodes = anatomy['nodes']
        actual = {(nodes[e['source']]['body_id'], nodes[e['target']]['body_id']): e['count']
                  for e in anatomy['links']}
        self.assertEqual(actual, expected)
        self.assertEqual(2 * 46 * 10 - len(actual), 158)
        self.assertTrue(all(count > 0 for count in actual.values()))

    def test_roiweight_does_not_use_whole_neuron_or_relative_weight(self):
        gen = self.generator()
        with gzip.open(DATA / 'hulse_er2epg.csv.gz', 'rt', newline='', encoding='utf-8') as stream:
            reader = csv.DictReader(stream)
            header = reader.fieldnames
            row = next(reader)
        row['weight'], row['weightRelative'], row['ROIweight'] = '999', '0.001', '3'
        stream = io.StringIO(newline='')
        writer = csv.DictWriter(stream, fieldnames=header)
        writer.writeheader()
        writer.writerow(row)
        nodes, edges = gen.extract_rows([('fixture.csv', stream.getvalue())])
        self.assertEqual(len(nodes), 2)
        self.assertEqual(edges[0]['synapse_count'], 3)

    def test_bad_rows_fail_closed(self):
        gen = self.generator()
        with gzip.open(DATA / 'hulse_er2epg.csv.gz', 'rt', newline='', encoding='utf-8') as stream:
            reader = csv.DictReader(stream)
            header, base = reader.fieldnames, next(reader)
        for key, value in [('ROIweight', '-1'), ('ROIweight', '0'), ('ROIweight', '1.5'),
                           ('ROIweight', 'NaN'), ('from', '123.0'), ('from', ''),
                           ('roi', 'PB'), ('name.from', ''), ('type.from', 'EPG_L')]:
            with self.subTest(key=key, value=value):
                row = dict(base, **{key: value})
                stream = io.StringIO(newline='')
                writer = csv.DictWriter(stream, fieldnames=header)
                writer.writeheader()
                writer.writerow(row)
                with self.assertRaises(ValueError):
                    gen.extract_rows([('fixture.csv', stream.getvalue())])

    def test_duplicate_rows_and_conflicting_node_annotations_rejected(self):
        gen = self.generator()
        with gzip.open(DATA / 'hulse_er2epg.csv.gz', 'rt', newline='', encoding='utf-8') as stream:
            reader = csv.DictReader(stream)
            header, row = reader.fieldnames, next(reader)
        for second in [row, dict(row, to='1', **{'name.from': 'ER4m(ring)_L'})]:
            stream = io.StringIO(newline='')
            writer = csv.DictWriter(stream, fieldnames=header)
            writer.writeheader()
            writer.writerows([row, second])
            with self.assertRaises(ValueError):
                gen.extract_rows([('fixture.csv', stream.getvalue())])

    def test_schema_rejects_unknown_fields_bad_indices_and_numeric_body_ids(self):
        gen = self.generator()
        good = json.loads(gen.generated(DATA)[gen.ANATOMY_NAME])
        mutations = [lambda d: d.update(activation=[]),
                     lambda d: d['nodes'][0].update(body_id=387364605),
                     lambda d: d['nodes'][0].update(angle=0),
                     lambda d: d['links'][0].update(count=True),
                     lambda d: d['links'][0].update(count=0),
                     lambda d: d['links'][0].update(source=56),
                     lambda d: d['links'][0].update(target=-1),
                     lambda d: d['links'][0].update(sign=-1),
                     lambda d: d['metadata'].update(roi='PB'),
                     lambda d: d['metadata']['license'].update(id='MIT')]
        for mutate in mutations:
            bad = copy.deepcopy(good)
            mutate(bad)
            with self.assertRaises(ValueError):
                gen.validate_anatomy(bad)

    def test_schema_counts_duplicates_and_cross_class_boundary(self):
        gen = self.generator()
        good = json.loads(gen.generated(DATA)[gen.ANATOMY_NAME])
        mutations = [lambda d: d['nodes'].pop(), lambda d: d['links'].pop(),
                     lambda d: d['nodes'].__setitem__(1, d['nodes'][0]),
                     lambda d: d['links'].__setitem__(1, d['links'][0]),
                     lambda d: d['links'][0].update(target=0),
                     lambda d: d['links'][0].update(count=d['links'][0]['count']+1)]
        for mutate in mutations:
            bad = copy.deepcopy(good)
            mutate(bad)
            with self.assertRaises(ValueError):
                gen.validate_anatomy(bad)

    def test_attribution_and_limitations_travel_with_json(self):
        gen = self.generator()
        metadata = json.loads(gen.generated(DATA)[gen.ANATOMY_NAME])['metadata']
        self.assertEqual(metadata['license']['id'], 'CC-BY-4.0')
        self.assertIn('creativecommons.org/licenses/by/4.0', metadata['license']['url'])
        self.assertIn('Hulse', metadata['license']['attribution'])
        self.assertIn('Scheffer', metadata['license']['attribution'])
        self.assertIn('No upstream analysis code', metadata['license']['repository_code_license'])
        self.assertIn('cross-class projection fragment', metadata['boundary'])
        text = ' '.join(metadata['limitations']).lower()
        for caution in ['within-class', 'external', 'missing', 'electrical', 'sign', 'geometry', 'dynamics']:
            self.assertIn(caution, text)

    def test_tampered_source_rejected_before_writing(self):
        gen = self.generator()
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            shutil.copytree(DATA, folder / 'data')
            raw = folder / 'data/hulse_er2epg.csv.gz'
            raw.write_bytes(raw.read_bytes() + b'\n')
            before = {p.name: p.read_bytes() for p in (folder / 'data').iterdir() if p.is_file()}
            for optimize in ([], ['-O']):
                result = subprocess.run([sys.executable, *optimize, str(GENERATOR),
                                         '--data-dir', str(folder / 'data')],
                                        capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('source', result.stderr.lower())
            after = {p.name: p.read_bytes() for p in (folder / 'data').iterdir() if p.is_file()}
            self.assertEqual(before, after)

    def test_compressed_sources_have_fixed_headers_and_verified_storage_hashes(self):
        gen = self.generator()
        for name, record in gen.SOURCES.items():
            self.assertIn('storage', record, 'Source storage must be pinned')
            storage = record['storage']
            contents = (DATA / storage['file']).read_bytes()
            self.assertEqual(storage['file'], name + '.gz')
            self.assertEqual(storage['compression'], 'gzip')
            self.assertEqual(contents[:10], bytes.fromhex('1f8b08000000000002ff'))
            self.assertEqual(hashlib.sha256(contents).hexdigest(), storage['sha256'])
            self.assertEqual(len(contents), storage['bytes'])
            self.assertFalse((DATA / name).exists(), 'Keep only compressed raw input')

    def test_cli_check_and_generation_are_reproducible_even_with_optimized_python(self):
        gen = self.generator()
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / 'data'
            shutil.copytree(DATA, folder)
            outputs = gen.generated(folder)
            for name in outputs:
                (folder / name).write_bytes(b'stale\n')
            result = subprocess.run([sys.executable, str(GENERATOR), '--check', '--data-dir', str(folder)],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('stale', result.stderr)
            for name in outputs:
                self.assertEqual((folder / name).read_bytes(), b'stale\n')
            result = subprocess.run([sys.executable, '-O', str(GENERATOR), '--data-dir', str(folder)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            for name in outputs:
                self.assertEqual((folder / name).read_bytes(), (DATA / name).read_bytes())
            result = subprocess.run([sys.executable, '-O', str(GENERATOR), '--check', '--data-dir', str(folder)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
