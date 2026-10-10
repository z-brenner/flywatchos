#!/usr/bin/env python3
"""Pin model evidence, metadata, generated signed table and fail-closed checks."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import generate_rate_reference as gen

class ReferenceProvenance(unittest.TestCase):
    def test_generated_artifacts_and_fixed_contract(self):
        table,model=gen.generated()
        self.assertEqual(gen.TABLE.read_bytes(),table.encode())
        self.assertEqual(gen.MODEL.read_bytes(),model.encode())
        data=json.loads(model)
        self.assertEqual(data['scope'],'host-only-source-equation-reference')
        self.assertFalse(data['hardware_verified'])
        self.assertEqual(data['node_count'],60); self.assertEqual(data['edge_count'],326)
        self.assertEqual(data['dt_ms'],.1); self.assertEqual(data['recurrent_gain'],.03)
        self.assertEqual(data['source_sha256'],gen.SOURCE_HASH)
        self.assertIn('/Kakaria_deBivort_2017/KakariaPBSimulationCode.v2/flyLI2.m',data['source_url'])
        self.assertEqual(data['license_notice'],(gen.DATA/'LICENSE').read_text())
        self.assertIn('Signed',data['units']); self.assertIn('not Hz',data['inputs']['units'])
        self.assertIn('noise is explicitly disabled',' '.join(data['limitations']))
        self.assertIn('{ 52u, 0u, -35.6772759590409 }',table)
        self.assertIn('{ 34u, 0u, 99.9680554605268 }',table)
    def test_stale_table_and_metadata_fail(self):
        with tempfile.TemporaryDirectory() as temporary:
            p=Path(temporary)/'stale';p.write_text('stale')
            for name in ('TABLE','MODEL'):
                with mock.patch.object(gen,name,p), mock.patch.object(sys,'argv',['generate','--check']):
                    with self.assertRaisesRegex(AssertionError,'stale'): gen.main()
    def test_changed_source_cannot_change_pinned_equation_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'flyLI2.m').write_text('modified')
            with mock.patch.object(gen,'DATA',root):
                with self.assertRaises(AssertionError):gen.generated()
    def test_optimized_python_fails_closed(self):
        for name in ('tools/generate_rate_reference.py','tests/generate_rate_reference_oracle.py'):
            result=subprocess.run([sys.executable,'-O',str(ROOT/name),'--check'],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0);self.assertIn('without -O/PYTHONOPTIMIZE',result.stderr)
    def test_fixture_binds_original_mat_and_rate_source(self):
        data=json.loads((ROOT/'tests/data/rate_reference_oracle.json').read_text())
        self.assertEqual(data['source_core_file_sha256'],gen.SOURCE_HASH)
        mat=gen.DATA/'connectivity_matrix_drosophila_mine_case_5_9cols_labels1.mat'
        self.assertEqual(data['source_mat_sha256'],hashlib.sha256(mat.read_bytes()).hexdigest())
        self.assertEqual(len(data['snapshots']['40000']),60)
        self.assertEqual(data['zero_input_after_40000_updates'],[0]*60)
    @unittest.skipUnless(importlib.util.find_spec('scipy'),'independent original-MAT oracle requires SciPy')
    def test_original_mat_si_equation_regenerates_full_fixtures(self):
        subprocess.run([sys.executable,str(ROOT/'tests/generate_rate_reference_oracle.py'),'--check'],check=True,timeout=60)
if __name__=='__main__':unittest.main()
