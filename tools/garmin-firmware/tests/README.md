# Offline Python tests

Run commands below from the repository root. Python 3.12 is the tested version.
The public checkout does not contain Garmin firmware, historical analysis
receipts, linked target binaries, or Ghidra projects. None is needed for the
public parser, allocation, fail-closed gate, or transaction-safety tests.

## Dependency-free allocation smoke check

```sh
python -B -m unittest discover -s tools/garmin-firmware/tests -p test_find_overlay_allocation.py -v
```

This small check uses only the Python standard library and synthetic data. It
covers candidate boundaries, pointer/branch references, malformed evidence,
incomplete coverage, and input/output collision protection. It is a focused
smoke check, not a replacement for the complete suite below.

## Complete discovery in a public checkout

Create a virtual environment rather than installing into system Python:

```sh
python -m venv /tmp/flywatchos-tests
/tmp/flywatchos-tests/bin/python -m pip install -r tools/garmin-firmware/tests/requirements.txt
/tmp/flywatchos-tests/bin/python -B -m unittest discover -s tools/garmin-firmware/tests -v
```

On Windows, use an environment outside the repository and its
`Scripts/python.exe` instead of `bin/python`. Installation needs access to a
package registry or a previously downloaded wheel cache. Test execution itself
does not download evidence or access a watch. Capstone and Unicorn are pinned
for the emulator and disassembly coverage; a missing dependency is an error,
not evidence of a passing integration test.

Public tests use synthetic temporary inputs and clean up temporary outputs.
Transaction and argument-rejection checks run independently of the private
integration classes. Do not infer firmware readiness, packaging permission,
or staging permission from a green public run.

## Private integration coverage

`private_fixtures.require_private_files` checks only the specifically declared
inputs of an integration test:

- A wholly absent fixture set is an explicit `private integration fixtures
  absent` skip, with the missing paths listed.
- A partially supplied set, empty file, directory in place of a file, dangling
  symlink, or filesystem access error makes the run fail.
- Present content reaches the existing hash, schema, byte-exact, and firmware
  assertions unchanged. Malformed JSON and wrong firmware bytes are never
  converted to skips.

Some tests have additional referenced inputs after their initial fixture
preflight. If those are missing, the existing validators still fail; the
preflight does not authorize incomplete evidence or catch validator errors.
Private receipts may pin test source hashes as well as firmware. Changes to a
pinned test require fresh, independently reviewed evidence before those
integration checks can pass; do not change historical receipts or production
hash pins merely to make a test green.

Private integration tests can invoke legacy target build scripts or write
analysis/package outputs. A public-checkout test run skips these before those
actions. Do not supply private fixtures or run that integration workflow unless
those actions are separately authorized. This test setup does not acquire,
build, regenerate, or publish private evidence for you.

Ghidra integration requires its local analyzed project and launcher. The N64
target integration additionally requires the historical PowerShell/ARM build
toolchain. Windows junction coverage is explicitly platform-specific, and
PowerShell staging rejection tests skip when `powershell` is absent; their
separate source-only guards still run. No missing tool relaxes a production
gate.

Unittest records a skipped `setUpClass` as one skip without counting the class's
test methods in `Ran N tests`. Therefore `N - skips` is not the number of passed
methods; use the individual verbose result lines when reporting that count.
