"""Real-process regressions for the public-only CI command runner."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

RUNNER = Path(__file__).with_name('run_offline_checks.py')


class RunnerTests(unittest.TestCase):
    def load_runner(self):
        self.assertTrue(RUNNER.is_file(), 'the shared CI command runner must exist')
        spec = importlib.util.spec_from_file_location('offline_checks', RUNNER)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_success_executes_every_command(self):
        runner = self.load_runner()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            commands = [[sys.executable, '-c', f"open('{name}', 'w').write('ok')"]
                        for name in ('first', 'second')]
            runner.run_commands(commands, root, timeout=10)
            self.assertEqual((root / 'first').read_text(), 'ok')
            self.assertEqual((root / 'second').read_text(), 'ok')

    def test_failure_stops_before_the_next_command(self):
        runner = self.load_runner()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            commands = [[sys.executable, '-c', 'raise SystemExit(7)'],
                        [sys.executable, '-c', "open('should-not-run', 'w').write('bad')"]]
            with self.assertRaises(subprocess.CalledProcessError) as error:
                runner.run_commands(commands, root, timeout=10)
            self.assertEqual(error.exception.returncode, 7)
            self.assertFalse((root / 'should-not-run').exists())

    def test_timeout_stops_before_the_next_command(self):
        runner = self.load_runner()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            commands = [[sys.executable, '-c', 'import time; time.sleep(10)'],
                        [sys.executable, '-c', "open('should-not-run', 'w').write('bad')"]]
            with self.assertRaises(subprocess.TimeoutExpired):
                runner.run_commands(commands, root, timeout=0.05)
            self.assertFalse((root / 'should-not-run').exists())

    def test_public_checkout_is_allowed(self):
        runner = self.load_runner()
        with tempfile.TemporaryDirectory() as directory:
            runner.require_public_checkout(Path(directory))

    def test_public_target_build_scripts_are_allowed(self):
        runner = self.load_runner()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'flyos/target/example'
            target.mkdir(parents=True)
            (target / 'build.ps1').write_text('# public source only')
            runner.require_public_checkout(root)

    def test_private_and_target_directories_are_rejected(self):
        runner = self.load_runner()
        for name in ('artifacts', 'flyos/target/example/build', 'tools/ghidra'):
            with self.subTest(path=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / name).mkdir(parents=True)
                with self.assertRaisesRegex(RuntimeError, 'public-only'):
                    runner.require_public_checkout(root)

    def test_optimized_python_is_rejected_before_checks(self):
        result = subprocess.run([sys.executable, '-B', '-O', str(RUNNER)],
                                capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('without -O/PYTHONOPTIMIZE', result.stderr)
        self.assertNotIn('Public offline checks passed', result.stdout)

    def test_dangling_private_symlink_is_rejected(self):
        runner = self.load_runner()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'artifacts').symlink_to(root / 'missing')
            with self.assertRaisesRegex(RuntimeError, 'public-only'):
                runner.require_public_checkout(root)


if __name__ == '__main__':
    unittest.main()
