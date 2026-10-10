#!/usr/bin/env python3
"""Run public, host-only checks after installing ci's pinned dependencies.

No dependency installation, firmware acquisition, target build, packaging,
watch access or publication is performed. Outputs use a fresh ignored directory.
"""
from __future__ import annotations

import importlib
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def require_public_checkout(root: Path) -> None:
    """Refuse known private inputs instead of accidentally running integration."""
    private_paths = [root / 'artifacts', root / 'tools/ghidra']
    private_paths.extend((root / 'flyos/target').glob('*/build'))
    private_paths.extend((root / 'flyos/target').glob('*/build-*'))
    if any(path.exists() or path.is_symlink() for path in private_paths):
        raise RuntimeError('This runner is public-only; use a separate public checkout '
                           'without artifacts, Ghidra tools or target build directories.')


def run_commands(commands: list[list[str]], cwd: Path, timeout: float = 300) -> None:
    """Keep real exit codes/timeouts fatal; never continue after a failed check."""
    for command in commands:
        print('+ ' + shlex.join(command), flush=True)
        subprocess.run(command, cwd=cwd, check=True, timeout=timeout)


def main() -> None:
    if sys.flags.optimize:
        raise RuntimeError('Run without -O/PYTHONOPTIMIZE so integrity assertions remain active.')
    require_public_checkout(ROOT)
    # SciPy is deliberately mandatory here; its independent MAT checks may not skip.
    for dependency in ('capstone', 'unicorn', 'ziglang', 'numpy', 'scipy.io'):
        importlib.import_module(dependency)
    python = sys.executable
    jsdom = str(ROOT / 'ci/node_modules/jsdom')
    run_commands([['node', '-e', "require(process.argv[1]);", jsdom]], ROOT)
    build_parent = ROOT / 'flyos/build'
    build_parent.mkdir(exist_ok=True)
    build = Path(tempfile.mkdtemp(prefix='offline-ci-', dir=build_parent))
    wasm = str(build / 'flyos-live.wasm')
    bundle = str(build / 'live-lab')
    commands = [
        [python, '-B', '-m', 'unittest', 'discover', '-s', 'ci', '-v'],
        ['cmake', '-S', 'flyos', '-B', str(build), '-DCMAKE_BUILD_TYPE=Debug',
         f'-DPython3_EXECUTABLE={python}'],
        ['cmake', '--build', str(build), '--parallel', '2'],
        ['ctest', '--test-dir', str(build), '--output-on-failure', '--timeout', '180',
         '--no-tests=error'],
        [python, '-B', 'flyos/tools/generate_cx_data.py', '--check'],
        [python, '-B', 'flyos/tools/build_live_wasm.py', '--output', wasm],
        ['node', 'flyos/tests/test_live_wasm.cjs', wasm, str(build / 'flyos-live-bridge-trace')],
        [python, '-B', 'flyos/tools/build_interaction_lab.py', '--exporter',
         str(build / 'flyos-interaction-exporter'), '--wasm', wasm, '--output', bundle],
        ['node', 'flyos/tests/test_interaction_lab_ui.cjs', str(Path(bundle) / 'index.html'), jsdom],
        ['node', 'flyos/tests/test_interaction_lab_circuit.cjs', jsdom],
        ['node', 'flyos/tests/test_interaction_lab_anatomy.cjs', jsdom],
        [python, '-B', '-m', 'unittest', 'discover', '-s', 'tools/garmin-firmware/tests', '-v'],
    ]
    run_commands(commands, ROOT)
    print(f'Public offline checks passed. Host-only outputs: {build}', flush=True)


if __name__ == '__main__':
    try:
        main()
    except subprocess.CalledProcessError as error:
        raise SystemExit(error.returncode if error.returncode > 0 else 1) from None
