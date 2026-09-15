import importlib.util
import json
import pathlib
import re
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[3]
TARGET = ROOT / "flyos" / "target" / "fr245_1370_neural_specimen_n64"
EMULATOR = ROOT / "tools" / "garmin-firmware" / "emulate_neural_specimen_n64.py"
RUNTIME = ROOT / "artifacts" / "firmware" / "analysis" / "fr245-1370-runtime-state.json"
BUTTON_DOC = ROOT / "docs" / "button-overlay-input.md"
RTC_DOC = ROOT / "docs" / "neural-overlay-placement.md"
SPEC = importlib.util.spec_from_file_location("flyos_n64_emulator", EMULATOR)
N64 = importlib.util.module_from_spec(SPEC); sys.modules[SPEC.name] = N64; SPEC.loader.exec_module(N64)

DIGITS = {
 "0":("111","101","101","101","111"), "1":("010","110","010","010","111"),
 "2":("110","001","010","100","111"), "3":("110","001","010","001","110"),
 "4":("101","101","111","001","001"), "5":("111","100","110","001","110"),
 "6":("011","100","111","101","111"), "7":("111","001","010","010","010"),
 "8":("111","101","111","101","111"), "9":("111","101","111","001","110")}
GLYPHS = {**DIGITS, "B":("110","101","110","101","110"),
 "M":("101","111","111","101","101"), "O":("010","101","101","101","010"),
 "T":("111","010","010","010","010"), "I":("111","010","010","010","111"),
 "N":("101","111","111","111","101"), "-":("000","000","111","000","000"), " ":("000",)*5}

class NeuralSpecimenN64TargetTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.sandbox=tempfile.TemporaryDirectory(prefix="flyos-n64-focused-"); cls.build=pathlib.Path(cls.sandbox.name)/"build"
  subprocess.run(["powershell","-NoProfile","-ExecutionPolicy","Bypass","-File",str(TARGET/"build.ps1"),"-BuildRoot",str(cls.build)],cwd=ROOT,check=True,capture_output=True,text=True)
  cls.bundle=N64.load_build(cls.build)
 @classmethod
 def tearDownClass(cls): cls.sandbox.cleanup()
 def assert_text(self,fb,x,y,value):
  for index,char in enumerate(value):
   for row,pattern in enumerate(GLYPHS[char]):
    for column,expected in enumerate(pattern): self.assertEqual(0x3F if expected=="1" else 0,fb[(y+row)*240+x+index*4+column])
   for row in range(5): self.assertEqual(0,fb[(y+row)*240+x+index*4+3])
 def test_exact_two_segment_layout_and_stack_ceiling(self):
  m=self.bundle.manifest; p=m["segments"]["primary"]["size"]; s=m["segments"]["secondary"]["size"]
  self.assertLessEqual(p,1023); self.assertLessEqual(s,2048); self.assertLessEqual(p+s,3071)
  self.assertEqual(0x1F63FF,m["repair_byte"]); self.assertEqual(384,m["stack_audit"]["stack_bound_bytes"])
  self.assertFalse(m["packaging_allowed"]); self.assertEqual(2,len(m["stack_audit"]["external_transfers"]))
 def test_build_manifest_is_clean_and_has_no_shared_test_oracles(self):
  N64.assert_build_clean(self.bundle.build,self.bundle.manifest)
  self.assertFalse((self.bundle.build/"oracle"/"tests").exists())
  retained=list((self.bundle.build/"oracle"/"retained").glob("*")); self.assertEqual(1,len(retained))
  with tempfile.TemporaryDirectory(prefix="flyos-n64-legacy-clean-") as directory:
   build=pathlib.Path(directory)/"build"; stale=build/"oracle"/"tests"/"legacy"; stale.mkdir(parents=True); (stale/"junk.bin").write_bytes(b"stale")
   subprocess.run(["powershell","-NoProfile","-ExecutionPolicy","Bypass","-File",str(TARGET/"build.ps1"),"-BuildRoot",str(build)],cwd=ROOT,check=True,capture_output=True,text=True)
   self.assertFalse((build/"oracle"/"tests").exists()); rebuilt=N64.load_build(build); N64.assert_build_clean(build,rebuilt.manifest)
 def test_stable_vendor_oracle_and_bounded_target_equivalence(self):
  expected={"valid":True,"empty":False,"not_home":False,"hidden_match":False,"multiple":True}
  for case,eligible in expected.items():
   with self.subTest(case=case):
    vendor=N64.vendor_view_oracle(case); self.assertEqual("returned",vendor["status"]); self.assertEqual(eligible,vendor["eligible"])
    self.assertEqual(eligible,N64.emulate(self.bundle,home=case)["eligible"])
  hazards={"malformed":("memory_fault",None),"cycle":("returned",True),"too_long":("returned",True)}
  for case,(status,eligible) in hazards.items():
   with self.subTest(case=case):
    vendor=N64.vendor_view_oracle(case); self.assertEqual(status,vendor["status"]); self.assertEqual(eligible,vendor["eligible"])
    result=N64.emulate(self.bundle,home=case,fill=0x6D); self.assertFalse(result["eligible"]); self.assertTrue(result["framebuffer_unchanged"])
 def test_detectable_view_mutations_fail_closed(self):
  for case in ("finder_mismatch","false_first_visible","root_mutation"):
   result=N64.emulate(self.bundle,home=case,fill=0x37); self.assertFalse(result["eligible"]); self.assertTrue(result["framebuffer_unchanged"]); self.assertEqual([],result["dirty_calls"])
 def test_all_home_failures_are_byte_identical_pass_through(self):
  for case in ("empty","malformed","cycle","too_long","not_home","hidden_match"):
   result=N64.emulate(self.bundle,home=case,fill=0x6D); self.assertFalse(result["eligible"]); self.assertTrue(result["framebuffer_unchanged"])
 def test_back_and_null_short_circuit(self):
  runtime=json.loads(RUNTIME.read_text()); back=int(runtime["signals"]["back_button_pass_through"]["source"]["pinned_addresses"][0],16)
  for case in ("valid","multiple","malformed"):
   result=N64.emulate(self.bundle,home=case,pressed_mask=4,fill=0x37); self.assertTrue(result["framebuffer_unchanged"]); self.assertEqual([[back,4]],result["data_reads"])
  null=N64.emulate(self.bundle,framebuffer_null=True); self.assertEqual([],null["data_reads"]); self.assertEqual([[0,0]],null["dispatch_calls"])
 def test_all_five_buttons_and_four_model_inputs(self):
  for bit in (1,2,8,16):
   result=N64.emulate(self.bundle,pressed_mask=bit); self.assertEqual(bit,result["buttons"]); self.assertEqual(64,result["verified_neuron_cells"])
  self.assertFalse(N64.emulate(self.bundle,pressed_mask=4)["eligible"])
 def test_io_addresses_derive_from_canonical_evidence_and_docs(self):
  runtime=json.loads(RUNTIME.read_text()); overlay=(TARGET/"overlay.c").read_text().lower(); signals=runtime["signals"]
  evidenced=[signals["back_button_pass_through"]["source"]["pinned_addresses"][0],signals["battery_percent"]["source"]["pinned_addresses"][0],signals["usb_mass_storage"]["source"]["pinned_addresses"][0],signals["watch_face_active"]["source"]["list_root"]]
  evidenced+=re.findall(r"0x400ff0(?:10|90|d0)|0x(?:00000800|00000400|00000002|00100000|00400000)",BUTTON_DOC.read_text(encoding="utf-8").lower())
  evidenced+=re.findall(r"0x4003d00[04]",RTC_DOC.read_text(encoding="utf-8").lower())
  for value in set(evidenced)-{"0x4003d004"}:
   token="2u" if value=="0x00000002" else value.lower()
   self.assertIn(token,overlay)
  self.assertEqual(5,len(N64.BUTTONS)); self.assertEqual(N64.RTC_SECONDS+4,N64.RTC_PRESCALER)
 def test_battery_binary32_and_exact_rail_glyphs(self):
  for value in (0,9,10,73,99,100):
   bits=struct.unpack("<I",struct.pack("<f",float(value)))[0]; result=N64.emulate(self.bundle,battery_bits=bits)
   self.assertEqual((4,value),(result["valid_mask"],result["battery"])); self.assert_text(result["framebuffer"],104,180,"B"); self.assert_text(result["framebuffer"],112,180,str(value))
  for value in (-1.0,-4.0,100.5,float("inf"),float("nan")):
   bits=struct.unpack("<I",struct.pack("<f",value))[0]; result=N64.emulate(self.bundle,battery_bits=bits); self.assertEqual((0,0),(result["valid_mask"],result["battery"]))
 def test_motion_unavailable_label_is_exact_and_safe(self):
  result=N64.emulate(self.bundle); self.assert_text(result["framebuffer"],59,190,"MOTION --"); self.assertTrue(result["safe_radius"])
 def test_usb_is_only_mass_storage_three_or_four(self):
  for state in range(7): self.assertEqual(int(state in (3,4)),N64.emulate(self.bundle,usb_state=state)["usb_ms"])
 def test_rtc_stable_retry_and_double_rollover(self):
  stable=N64.emulate(self.bundle,rtc_samples=[(7,0x8123,7)]); self.assertEqual(((7<<15)|0x123,3),(stable["tick"],stable["rtc_reads"]))
  retry=N64.emulate(self.bundle,rtc_samples=[(7,9,8),(8,0xFFFF,8)]); self.assertEqual(((8<<15)|0x7FFF,6),(retry["tick"],retry["rtc_reads"]))
  failed=N64.emulate(self.bundle,rtc_samples=[(7,9,8),(8,10,9)]); self.assertEqual((0xFFFFFFFF,6),(failed["tick"],failed["rtc_reads"]))
 def test_calls_registers_canaries_stack_and_exact_reads(self):
  result=N64.emulate(self.bundle,home="multiple"); self.assertEqual([[0,0,240,240]],result["dirty_calls"]); self.assertEqual([[N64.FRAMEBUFFER,0]],result["dispatch_calls"]); self.assertEqual([N64.DIRTY,N64.DISPATCH],result["external_targets"])
  for key in ("callee_saved_preserved","sp_restored","guard_before_unchanged","guard_after_unchanged"): self.assertTrue(result[key])
  self.assertLessEqual(result["maximum_runtime_stack_bytes"],384); self.assertEqual([],result["outside_writes"])
  fixed={N64.VIEW_ROOT,N64.GPIOD,N64.GPIOA,N64.GPIOC,N64.BATTERY,N64.USB_MS,N64.RTC_SECONDS,N64.RTC_PRESCALER}; nodes={0x20001000,0x20001100}
  for address,size in result["data_reads"]:
   self.assertEqual(1 if address==N64.USB_MS else 4,size); self.assertTrue(address in fixed or any(address==n+o for n in nodes for o in (4,8,0x50)))
 def test_all_intersegment_branches_execute(self):
  audit=self.bundle.manifest["stack_audit"]["cross_segment_branches"]; seen=set()
  for fixture in [dict(),dict(battery_bits=0x42C80000)]+[dict(pressed_mask=b) for b in (1,2,8,16)]: seen.update(tuple(p) for p in N64.emulate(self.bundle,**fixture)["executed_cross_segment_branches"])
  self.assertEqual({tuple(p) for p in audit},seen)
 def test_64_cells_and_host_semantic_oracle(self):
  result=N64.emulate(self.bundle,pressed_mask=2,battery_bits=0x42C80000,usb_state=4); oracle=N64.host_oracle(self.bundle.build,result["tick"],2,1,100,1)
  self.assertEqual(oracle["brain"],result["brain"]); self.assertEqual(oracle["target_framebuffer"],result["framebuffer"]); self.assertEqual(64,N64.verify_cells(result["framebuffer"],result["activation"]))
 def test_all_six_exact_palette_roles_include_forced_saturated_cell(self):
  result=N64.emulate(self.bundle,forced_activation=(56,700)); self.assertTrue(result["all_pixels_reviewed_palette"]); self.assertEqual({0,12,42,51,56,63},set(result["framebuffer"]))
  self.assertEqual({0x38},{result["framebuffer"][(135+r)*240+96+c] for r in range(5) for c in range(5)})
 def test_title_and_state_are_present_inside_safe_radius(self):
  result=N64.emulate(self.bundle); self.assertTrue(result["safe_radius"]); rows=("010","101","111","101","101")
  for row,pattern in enumerate(rows):
   for col,expected in enumerate(pattern): self.assertEqual(0x3F if expected=="1" else 0,result["framebuffer"][(18+row)*240+118+col])
  self.assertGreater(sum(v==0x3F for v in result["framebuffer"][190*240:195*240]),4)
 def test_deterministic_runtime_and_two_clean_isolated_builds(self):
  a=N64.emulate(self.bundle,pressed_mask=16,usb_state=3); b=N64.emulate(self.bundle,pressed_mask=16,usb_state=3); self.assertEqual((a["framebuffer_sha256"],a["write_trace_sha256"]),(b["framebuffer_sha256"],b["write_trace_sha256"]))
  with tempfile.TemporaryDirectory(prefix="flyos-n64-rebuild-") as directory:
   roots=[pathlib.Path(directory)/name for name in ("a","b")]
   for root in roots: subprocess.run(["powershell","-NoProfile","-ExecutionPolicy","Bypass","-File",str(TARGET/"build.ps1"),"-BuildRoot",str(root)],cwd=ROOT,check=True,capture_output=True,text=True)
   for name in (N64.ELF_NAME,"hook.bin","primary.bin","secondary.bin","manifest.json","SHA256SUMS.txt"): self.assertEqual((roots[0]/name).read_bytes(),(roots[1]/name).read_bytes(),name)
 def test_deterministic_report_previews_and_evidence_manifest(self):
  with tempfile.TemporaryDirectory(prefix="flyos-n64-evidence-") as directory:
   roots=[pathlib.Path(directory)/name for name in ("a","b")]
   for root in roots: N64.publish_evidence(self.bundle.build,root)
   names=sorted(path.name for path in roots[0].iterdir()); self.assertIn("fr245-1370-n64-evidence-manifest.json",names)
   self.assertEqual(names,sorted(path.name for path in roots[1].iterdir()))
   for name in names: self.assertEqual((roots[0]/name).read_bytes(),(roots[1]/name).read_bytes(),name)
   manifest=json.loads((roots[0]/"fr245-1370-n64-evidence-manifest.json").read_text(encoding="utf-8"))
   self.assertNotIn("fr245-1370-n64-evidence-manifest.json",manifest["files"])
   for name,item in manifest["files"].items(): self.assertEqual(item["sha256"],N64.sha256((roots[0]/name).read_bytes()))
   report=json.loads((roots[0]/"fr245-1370-n64-emulator-report.json").read_text(encoding="utf-8"))
   self.assertEqual([0,12,42,51,56,63],report["palette"]["saturated_fixture"]["pixels_present"])
 def test_no_float_or_forbidden_storage_and_allocation_mutation(self):
  listing=(self.bundle.build/"fr245-1370-neural-specimen-n64.disassembly.txt").read_text().lower()
  for token in ("vadd","vsub","vmul","vdiv","vcvt","__aeabi_f"): self.assertNotIn(token,listing)
  sections,_=N64.read_elf(self.bundle.build/N64.ELF_NAME); self.assertTrue(".forbidden" not in sections or sections[".forbidden"]["size"]==0)
  original=N64.ALLOCATION
  with tempfile.TemporaryDirectory() as directory:
   path=pathlib.Path(directory)/"allocation.json"; data=json.loads(original.read_text()); data["third_allocation_used"]=True; path.write_text(json.dumps(data)); N64.ALLOCATION=path
   try:
    with self.assertRaisesRegex(ValueError,"canonical"): N64.evidence_gate()
   finally: N64.ALLOCATION=original

if __name__=="__main__": unittest.main()
