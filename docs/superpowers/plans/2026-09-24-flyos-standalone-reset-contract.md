# FlyOS Standalone Reset Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recover and validate the FR245 13.70 application reset root and its bounded early-startup dependencies as a fail-closed contract for standalone FlyOS.

**Architecture:** A small Python front end pins the official application bytes, decodes the reset trampoline, launches a fresh read-only Ghidra analysis, and adjudicates the resulting call/MMIO inventory. Private instruction/decompiler evidence stays under ignored `artifacts/`; only a sanitized receipt containing hashes, addresses, classifications, and gate results is committed.

**Tech Stack:** Python 3.12, `unittest`, Capstone 5, Ghidra 12.1.3 headless Java scripts, PowerShell, ARM Thumb/Cortex-M4.

**Spec:** `docs/superpowers/specs/2026-09-24-flyos-standalone-k28-design.md`

## Global Constraints

- The Garmin resident loader below `0x00003000` remains unmodified.
- No GarminOS application instruction or service may be a runtime dependency of the final standalone image.
- Every target MMIO write needs a source-image hash, source address, instruction bytes/hash, address/width/value facts, ordering, preconditions, and confidence grade.
- Unknown or dynamically unresolved writes remain unknown; they are never converted into target code.
- Proprietary firmware, decompiler text, full instruction listings, personal data, and device identifiers remain under ignored `artifacts/` and are never committed or uploaded.
- This plan creates analysis reports only. It must not create a GCD, enable packaging/staging, access the mounted watch, or invoke `tools/live-proof/stage-gupdate.ps1`.
- Output paths use create-new semantics. Existing evidence is never overwritten or deleted.
- A Ghidra zero exit code is insufficient: every required output must exist, parse, identify the pinned image, and pass schema validation.

## Review Focus

- A wrong 5,079,040-byte image must fail on SHA-256 before any reset or MMIO claim is emitted; Task 1 pins this with a same-size mutation test.
- An even, erased, or out-of-range stage-two pointer at `0x0000320c` must fail closed; Task 1 tests all three cases.
- Ghidra may exit zero after a post-script error or omit an output; Task 2 tests missing/malformed output and explicit collision refusal.
- Indirect calls, computed MMIO addresses, or unbounded polling in the startup closure must keep `go=false`; Task 3 tests each condition independently.
- Public receipts must not leak proprietary disassembly or local private paths; Task 4 tests the sanitized schema and forbidden-string/path scan.

---

### Task 1: Immutable reset-root extractor

**Files:**
- Create: `tools/garmin-firmware/k28_reset_contract.py`
- Create: `tools/garmin-firmware/tests/test_k28_reset_contract.py`

**Interfaces:**
- Consumes: pinned application bytes at `artifacts/firmware/analysis/Forerunner245_1370_GUPDATE/stream_01_fw_all_bin.bin`.
- Produces: `ResetRoot` and `load_reset_root(root: Path) -> ResetRoot`; CLI root JSON with no MMIO conclusions.

- [ ] **Step 1: Write failing root and fail-closed input tests**

```python
class ResetRootTests(unittest.TestCase):
    def test_pinned_reset_root(self):
        root = contract.load_reset_root(ROOT)
        self.assertEqual(contract.PINNED_IMAGE_SHA256, root.image_sha256)
        self.assertEqual(0x31F1, root.reset_vector)
        self.assertEqual(0x31F0, root.reset_handler)
        self.assertEqual(0x19341, root.stage2_pointer)
        self.assertEqual(0x19340, root.stage2_entry)
        self.assertEqual(
            "72b64ff0000080f31488bff36f8fdff808d002480047",
            root.reset_bytes.hex(),
        )

    def test_same_size_image_mutation_is_rejected_before_decode(self):
        damaged = bytearray(contract.pinned_image_path(ROOT).read_bytes())
        damaged[0x1F0] ^= 1
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            contract.decode_pinned_image(bytes(damaged))

    def test_stage2_pointer_must_be_thumb_and_inside_application(self):
        image = bytearray(contract.pinned_image_path(ROOT).read_bytes())
        for pointer in (0x19340, 0xFFFFFFFF, 0x00200001):
            with self.subTest(pointer=pointer):
                changed = bytearray(image)
                changed[0x20C:0x210] = pointer.to_bytes(4, "little")
                with self.assertRaises(ValueError):
                    contract.decode_trusted_layout(bytes(changed))
```

- [ ] **Step 2: Run the focused tests and confirm they fail**

Run: `python -B -m unittest -v tools/garmin-firmware/tests/test_k28_reset_contract.py`

Expected: import failure because `k28_reset_contract.py` does not exist.

- [ ] **Step 3: Implement the pinned loader and reset decoder**

```python
APP_BASE = 0x00003000
APP_END_EXCLUSIVE = 0x00200000
PINNED_IMAGE_SIZE = 5_079_040
PINNED_IMAGE_SHA256 = "b45be1baf98999af10f073bef52b284beb2aea6abbb7cde2ffa59fb6bcedeab6"
RESET_VECTOR_OFFSET = 4
RESET_HANDLER = 0x000031F0
RESET_HANDLER_OFFSET = RESET_HANDLER - APP_BASE
RESET_HANDLER_SIZE = 22
STAGE2_LITERAL_VA = 0x0000320C
STAGE2_LITERAL_OFFSET = STAGE2_LITERAL_VA - APP_BASE
EXPECTED_RESET_BYTES = bytes.fromhex(
    "72b64ff0000080f31488bff36f8fdff808d002480047"
)

@dataclasses.dataclass(frozen=True)
class ResetRoot:
    image_sha256: str
    reset_vector: int
    reset_handler: int
    reset_bytes: bytes
    stage2_pointer: int
    stage2_entry: int

def decode_trusted_layout(image: bytes) -> ResetRoot:
    if len(image) != PINNED_IMAGE_SIZE:
        raise ValueError("pinned image size mismatch")
    reset_vector = int.from_bytes(image[4:8], "little")
    reset_bytes = image[
        RESET_HANDLER_OFFSET:RESET_HANDLER_OFFSET + RESET_HANDLER_SIZE
    ]
    stage2_pointer = int.from_bytes(
        image[STAGE2_LITERAL_OFFSET:STAGE2_LITERAL_OFFSET + 4], "little"
    )
    if reset_vector != RESET_HANDLER | 1:
        raise ValueError("reset vector mismatch")
    if reset_bytes != EXPECTED_RESET_BYTES:
        raise ValueError("reset handler bytes mismatch")
    if stage2_pointer & 1 == 0:
        raise ValueError("stage-two pointer is not Thumb")
    stage2_entry = stage2_pointer & ~1
    if not APP_BASE <= stage2_entry < APP_END_EXCLUSIVE:
        raise ValueError("stage-two entry outside application")
    return ResetRoot("", reset_vector, RESET_HANDLER, reset_bytes,
                     stage2_pointer, stage2_entry)
```

`decode_pinned_image` computes and checks SHA-256 before calling
`decode_trusted_layout`; `load_reset_root` reads only the fixed repository path.
Use Capstone only to assert the root disassembles completely in Thumb/M-class
mode and terminates with `bx r0`; do not infer stage-two semantics here.

- [ ] **Step 4: Add create-new root-report CLI behavior**

```python
def write_new_json(path: Path, value: dict) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")
```

CLI: `python -B tools/garmin-firmware/k28_reset_contract.py root --output <new.json>`.
Add tests proving an existing output remains byte-identical and the CLI exits 2.

- [ ] **Step 5: Run focused tests**

Run: `python -B -m unittest -v tools/garmin-firmware/tests/test_k28_reset_contract.py`

Expected: all Task 1 tests pass.

- [ ] **Step 6: Commit**

```powershell
git add -- tools/garmin-firmware/k28_reset_contract.py tools/garmin-firmware/tests/test_k28_reset_contract.py
git commit -m "analysis: pin standalone reset root"
```

### Task 2: Fresh Ghidra startup inventory

**Files:**
- Create: `tools/garmin-firmware/ghidra_scripts/K28ResetContractReport.java`
- Create: `tools/garmin-firmware/run_k28_reset_contract.ps1`
- Modify: `tools/garmin-firmware/k28_reset_contract.py`
- Modify: `tools/garmin-firmware/tests/test_k28_reset_contract.py`

**Interfaces:**
- Consumes: `ResetRoot.stage2_entry`, the pinned image, Ghidra 12.1.3, and a create-new output directory.
- Produces: private `ghidra-inventory.json`, `decompilation.txt`, `headless.log`, and `script.log`; `load_ghidra_inventory(path: Path) -> dict`.

- [ ] **Step 1: Write failing launcher and inventory tests**

```python
class GhidraInventoryTests(unittest.TestCase):
    def test_inventory_requires_pinned_program_and_stage2(self):
        report = fixture_inventory()
        contract.validate_ghidra_inventory(report, fixture_root())
        report["program"]["sha256"] = "00" * 32
        with self.assertRaisesRegex(ValueError, "program SHA-256"):
            contract.validate_ghidra_inventory(report, fixture_root())

    def test_inventory_requires_every_output_and_rejects_postscript_error(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            (run / "ghidra-inventory.json").write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing evidence output"):
                contract.load_ghidra_run(run, fixture_root())

    def test_launcher_refuses_any_existing_run_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            occupied = Path(directory) / "run"
            occupied.mkdir()
            sentinel = occupied / "sentinel"
            sentinel.write_bytes(b"preserve")
            result = subprocess.run(
                ["powershell", "-ExecutionPolicy", "Bypass", "-File",
                 str(RUNNER), "-OutputRoot", str(occupied)],
                capture_output=True, text=True,
            )
            self.assertNotEqual(0, result.returncode)
            self.assertEqual(b"preserve", sentinel.read_bytes())
```

- [ ] **Step 2: Run tests and confirm the new cases fail**

Run: `python -B -m unittest -v tools/garmin-firmware/tests/test_k28_reset_contract.py`

Expected: failures for missing runner, validator, and fixture schema.

- [ ] **Step 3: Implement the headless runner with a fresh scratch project**

`run_k28_reset_contract.ps1` must:

```powershell
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$OutputRoot)
$ErrorActionPreference = 'Stop'
if (Test-Path -LiteralPath $OutputRoot) { throw 'output collision' }
New-Item -ItemType Directory -Path $OutputRoot | Out-Null
$project = Join-Path $OutputRoot 'ghidra-project'
$inventory = Join-Path $OutputRoot 'ghidra-inventory.json'
$decompilation = Join-Path $OutputRoot 'decompilation.txt'
```

It imports only the pinned image as ARM Cortex-M at base `0x3000`, uses
`SeedCortexM.java 0x3000 124` and `SeedThumbFunctions.java 0x19340` before
analysis, runs `K28ResetContractReport.java`, and fails unless all four evidence
files exist and neither log contains `SCRIPT ERROR`, `post-script`, or
`output collision`. It never opens the persistent Ghidra project for writing.

- [ ] **Step 4: Implement the bounded Ghidra exporter**

`K28ResetContractReport.java` takes `<inventory.json> <decompilation.txt>
<stage2-address> <max-depth>`. It must:

```java
private boolean isMmio(Address address) {
    long value = address.getOffset();
    return (value >= 0x40000000L && value < 0x60000000L) ||
           (value >= 0xe0000000L && value < 0xe0100000L);
}
```

- hash the mapped `0x3000..0x1fffff` bytes and require the pinned SHA-256;
- start from reset `0x31f0` and stage two `0x19340`;
- traverse direct callees to depth 3, sorted by address;
- export each function entry/end, SHA-256 of its bytes, direct calls, indirect
  control-flow instructions, literal/data references, MMIO references, and
  backward branches;
- emit decompiler text only to the private decompilation output;
- write outputs with `CREATE_NEW` and reject collisions;
- include `analysis_complete`, `cancelled`, and unresolved seed/function counts.

Do not label an MMIO transaction's value or purpose in Java; that classification
belongs to Task 3.

- [ ] **Step 5: Implement strict Python inventory loading**

```python
REQUIRED_GHIDRA_OUTPUTS = (
    "ghidra-inventory.json", "decompilation.txt", "headless.log", "script.log"
)

def load_ghidra_run(run: Path, root: ResetRoot) -> dict:
    missing = [name for name in REQUIRED_GHIDRA_OUTPUTS if not (run / name).is_file()]
    if missing:
        raise ValueError(f"missing evidence output: {missing}")
    logs = (run / "headless.log").read_text(errors="replace") + \
           (run / "script.log").read_text(errors="replace")
    if "SCRIPT ERROR" in logs:
        raise ValueError("Ghidra post-script error")
    report = json.loads((run / "ghidra-inventory.json").read_text())
    validate_ghidra_inventory(report, root)
    return report
```

- [ ] **Step 6: Run focused unit tests**

Run: `python -B -m unittest -v tools/garmin-firmware/tests/test_k28_reset_contract.py`

Expected: all unit tests pass without requiring the private Ghidra project.

- [ ] **Step 7: Run one real fresh Ghidra inventory**

Run:

```powershell
$run = 'C:\Users\zgbre\artifacts\firmware\analysis\standalone-reset-contract-2026-09-24'
powershell -ExecutionPolicy Bypass -File tools/garmin-firmware/run_k28_reset_contract.ps1 -OutputRoot $run
python -B tools/garmin-firmware/k28_reset_contract.py inventory --run $run
```

Expected: pinned source hash, reset `0x31f0`, stage two `0x19340`, all required
outputs, and no Ghidra script error. If the fixed run path already exists, use a
new date/time-suffixed directory; never overwrite the old one.

- [ ] **Step 8: Commit**

```powershell
git add -- tools/garmin-firmware/ghidra_scripts/K28ResetContractReport.java tools/garmin-firmware/run_k28_reset_contract.ps1 tools/garmin-firmware/k28_reset_contract.py tools/garmin-firmware/tests/test_k28_reset_contract.py
git commit -m "analysis: inventory standalone reset closure"
```

### Task 3: Fail-closed contract adjudicator

**Files:**
- Modify: `tools/garmin-firmware/k28_reset_contract.py`
- Modify: `tools/garmin-firmware/tests/test_k28_reset_contract.py`
- Create: `flyos/target/k28/contracts/fr245_1370_reset_root.json`

**Interfaces:**
- Consumes: validated private Ghidra inventory.
- Produces: `build_contract(root: ResetRoot, inventory: dict) -> dict` and a sanitized public receipt with explicit gates and `go`.

- [ ] **Step 1: Write failing gate and sanitization tests**

```python
class ContractGateTests(unittest.TestCase):
    def test_unresolved_control_flow_fails_closed(self):
        inventory = fixture_inventory()
        inventory["functions"][0]["indirect_control_flow"] = ["0x1934c"]
        report = contract.build_contract(fixture_root(), inventory)
        self.assertFalse(report["gates"]["control_flow_closed"])
        self.assertFalse(report["go"])

    def test_computed_mmio_and_unbounded_polling_fail_independently(self):
        for mutation, gate in (
            (("computed_mmio", ["0x40000000+r3"]), "mmio_addresses_closed"),
            (("unbounded_polls", ["0x191f0"]), "polls_bounded"),
        ):
            inventory = fixture_inventory()
            inventory[mutation[0]] = mutation[1]
            report = contract.build_contract(fixture_root(), inventory)
            self.assertFalse(report["gates"][gate])
            self.assertFalse(report["go"])

    def test_public_receipt_contains_no_code_or_private_paths(self):
        receipt = contract.sanitize_contract(fixture_complete_contract())
        encoded = json.dumps(receipt).lower()
        for forbidden in ("decompilation", "instruction_text", "c:\\\\users",
                          "artifacts/firmware", "stream_01_fw_all_bin.bin"):
            self.assertNotIn(forbidden, encoded)
```

- [ ] **Step 2: Run tests and confirm the gate cases fail**

Run: `python -B -m unittest -v tools/garmin-firmware/tests/test_k28_reset_contract.py`

Expected: failures because `build_contract` and `sanitize_contract` do not exist.

- [ ] **Step 3: Implement explicit independent gates**

```python
def build_contract(root: ResetRoot, inventory: dict) -> dict:
    gates = {
        "pinned_source": inventory["program"]["sha256"] == root.image_sha256,
        "reset_root_exact": inventory["roots"] == ["0x000031f0", "0x00019340"],
        "analysis_complete": bool(inventory["analysis_complete"]) and
                             not inventory["cancelled"],
        "control_flow_closed": not any(
            function["indirect_control_flow"] for function in inventory["functions"]
        ),
        "mmio_addresses_closed": not inventory["computed_mmio"],
        "mmio_widths_closed": not inventory["unknown_mmio_widths"],
        "mmio_values_closed": not inventory["unknown_mmio_values"],
        "polls_bounded": not inventory["unbounded_polls"],
        "memory_ranges_closed": not inventory["unknown_memory_ranges"],
    }
    return {
        "schema_version": 1,
        "source_sha256": root.image_sha256,
        "reset_handler": "0x000031f0",
        "stage2_entry": "0x00019340",
        "functions": inventory["functions"],
        "gates": gates,
        "go": all(gates.values()),
    }
```

Classification must preserve `unknown` instead of guessing function purposes.
The real first run is expected to remain `go=false` until direct-call and MMIO
semantics are closed by evidence; a fail-closed report is a valid task result.

- [ ] **Step 4: Implement a sanitized public receipt**

The committed receipt includes only source hash, root addresses, function entry
and byte hashes, counts, named gates, evidence grades, and `go`. Strip absolute
paths, instruction/decompiler text, literal bytes beyond the 22-byte reset root,
and any raw firmware-derived tables.

- [ ] **Step 5: Run tests and generate the receipt from the real inventory**

Run:

```powershell
python -B -m unittest -v tools/garmin-firmware/tests/test_k28_reset_contract.py
python -B tools/garmin-firmware/k28_reset_contract.py contract --run $run --output flyos/target/k28/contracts/fr245_1370_reset_root.json
```

Expected: tests pass. The CLI reports `go=true` only if every independent gate
is proved; otherwise it reports the exact false gates and exits 1 after writing
the honest receipt.

- [ ] **Step 6: Commit**

```powershell
git add -- tools/garmin-firmware/k28_reset_contract.py tools/garmin-firmware/tests/test_k28_reset_contract.py flyos/target/k28/contracts/fr245_1370_reset_root.json
git commit -m "analysis: gate standalone reset contract"
```

### Task 4: Document the reset-contract result and stop at the gate

**Files:**
- Modify: `flyos/target/k28/README.md`
- Create: `docs/standalone-reset-contract.md`
- Modify: `.superpowers/sdd/2026-09-15-flyos-n64-atlas-shell/progress.md` (local ignored ledger only)
- Test: `tools/garmin-firmware/tests/test_k28_reset_contract.py`

**Interfaces:**
- Consumes: sanitized receipt and private report hashes.
- Produces: public evidence-level narrative and an explicit next-plan gate; no target MMIO code.

- [ ] **Step 1: Add failing documentation-consistency tests**

```python
def test_public_docs_match_committed_receipt(self):
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    document = RESET_DOC.read_text(encoding="utf-8")
    self.assertIn(receipt["source_sha256"], document)
    self.assertIn(f"`go={str(receipt['go']).lower()}`", document)
    for name, value in receipt["gates"].items():
        self.assertIn(f"| `{name}` | `{str(value).lower()}` |", document)

def test_public_docs_and_receipt_have_no_private_evidence_paths(self):
    combined = (RESET_DOC.read_text(encoding="utf-8") +
                RECEIPT.read_text(encoding="utf-8")).lower()
    self.assertNotIn("c:\\\\users", combined)
    self.assertNotIn("artifacts/firmware", combined)
```

- [ ] **Step 2: Run the tests and confirm documentation is missing**

Run: `python -B -m unittest -v tools/garmin-firmware/tests/test_k28_reset_contract.py`

Expected: failure because `docs/standalone-reset-contract.md` does not exist.

- [ ] **Step 3: Write the evidence report and update the K28 README**

`docs/standalone-reset-contract.md` must state:

- confirmed reset vector/handler/stage-two addresses and source SHA-256;
- one table row for every gate, copied from the receipt;
- separate confirmed, strongly inferred, unknown, and refuted sections;
- private report SHA-256 values without private paths;
- that `go=false` blocks target MMIO implementation, if any gate is false;
- that `go=true` authorizes only the next offline BSP plan, never packaging or
  a live write.

Update `flyos/target/k28/README.md` to link the report and replace statements
made obsolete by the new evidence. Do not claim a clock, watchdog, panel, or
recovery contract that the gates do not prove.

- [ ] **Step 4: Run focused, host, and K28 baseline verification**

Run:

```powershell
python -B -m unittest -v tools/garmin-firmware/tests/test_k28_reset_contract.py
cmake --build flyos/build --config Release
ctest --test-dir flyos/build -C Release --output-on-failure
powershell -ExecutionPolicy Bypass -File flyos/target/k28/build.ps1
git diff --check
```

Expected: all reset-contract tests pass, 7/7 host tests pass, K28 structural
build passes, and the diff check is clean.

- [ ] **Step 5: Update the local SDD ledger with evidence grades and exact commands**

Record the branch, commits, private report hashes, receipt hash, test counts,
gate results, and the explicit stop/proceed ruling. Never add the ignored ledger
with `git add -f`.

- [ ] **Step 6: Commit and push the branch**

```powershell
git add -- flyos/target/k28/README.md docs/standalone-reset-contract.md tools/garmin-firmware/tests/test_k28_reset_contract.py
git commit -m "docs: record standalone reset contract"
git push -u origin feat/flyos-standalone-k28
```

Stop after this commit. If `go=false`, the next work is a focused evidence plan
for the exact false gates. If `go=true`, the next work is the separately reviewed
Milestone B board-support-package plan. Neither outcome authorizes a GCD or watch
write.
