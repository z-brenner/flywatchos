# Public offline checks

GitHub Actions runs `.github/workflows/offline-checks.yml` on pushes, pull
requests and manual dispatch. It grants only `contents: read`, checks out
without retaining credentials, uses full action commit pins, and has bounded
job/command timeouts and cancel-on-newer-run concurrency. It does not publish
artifacts, deploy, request secrets or credentials, or acquire private inputs.

## Run the same checks locally

Use a **public-only checkout** and Linux with a C compiler, Python 3.12.14 and
Node 24.19.0 available. From the repository root:

```sh
python3 -m venv /tmp/flywatchos-ci
. /tmp/flywatchos-ci/bin/activate
python -m pip install --only-binary=:all: -r ci/requirements.txt
npm ci --prefix ci --ignore-scripts --no-audit --no-fund
python -B ci/run_offline_checks.py
```

Dependency setup needs public package registries or a prepopulated local cache.
The runner does not install packages or download evidence. Tests use bundled
public data and synthetic inputs. This is not a network-isolation sandbox.

The requirements pin CMake, Zig, NumPy and SciPy, and include the existing pinned
Capstone/Unicorn requirements. The npm lockfile pins jsdom and its complete
transitive dependency tree, including registry integrity hashes. The Ubuntu
runner image and its host C compiler still receive GitHub image updates; this
workflow is repeatable verification, not a bit-for-bit reproducible OS image.

Each run writes a fresh `flyos/build/offline-ci-*` directory, preserving prior
captures and printing the new output path on success. A failed command stops
the runner and returns failure. The C build uses Debug so C assertions remain
active. Optimized Python is rejected. Each command is limited to five minutes;
individual CTest tests also have a three-minute limit.

## Coverage and boundaries

- All CMake/CTest host tests, including automatically registered new tests
- CX60 source/table checks and independent MAT re-extraction with SciPy required
- A real import-free C/WebAssembly build and native/Wasm differential checks
- A self-contained live bundle and all jsdom state/circuit/anatomy suites
- Complete public firmware-tool unittest discovery with synthetic inputs
- Runner regressions for stop-on-failure, timeout and public-only guards

`artifacts/`, `tools/ghidra/` and target build directories must be absent,
including dangling symlinks. The runner refuses these known private-input
locations before invoking any tests; use a separate public checkout rather than
removing or moving private evidence. No private integration test is promoted to
a pass: genuine private/platform skips remain visible in unittest output.

This check is host-only. It is not a firmware build, firmware package, staging
operation, flash, device interaction, biological validation, target safety
approval or browser visual QA. A green local run does not establish that the
hosted workflow has run; check the exact published commit's Actions result.

## Pin references

The action pins were verified against their official release commits:

- [actions/checkout v5.0.0](https://github.com/actions/checkout/commit/08c6903cd8c0fde910a37f88322edcfb5dd907a8)
- [actions/setup-python v6.0.0](https://github.com/actions/setup-python/commit/e797f83bcb11b83ae66e0230d6156d7c80228e7c)
- [actions/setup-node v6.0.0](https://github.com/actions/setup-node/commit/2028fbc5c25fe9cf00d9f06a71cc4710d4507903)
- [GitHub workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)

Update dependencies deliberately and rerun the complete command above.
