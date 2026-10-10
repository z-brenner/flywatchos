"""Preflight local integration fixtures without changing production gates."""

import stat
import unittest
from pathlib import Path


def require_private_files(*paths):
    """Skip only a wholly absent fixture set; never hide partial/bad evidence.

    Content validation remains in the test and the production validators. In
    particular, do not catch their JSON, hash, schema, or firmware errors.
    ``lstat`` distinguishes a dangling symlink from a genuinely absent input.
    """
    if not paths:
        raise ValueError("at least one private fixture is required")
    missing = []
    for path in map(Path, paths):
        try:
            path.lstat()
        except FileNotFoundError:
            missing.append(path)
            continue
        try:
            info = path.stat()
        except FileNotFoundError:
            raise AssertionError(f"private fixture is not a regular file: {path}") from None
        if not stat.S_ISREG(info.st_mode):
            raise AssertionError(f"private fixture is not a regular file: {path}")
        if info.st_size == 0:
            raise AssertionError(f"private fixture is empty: {path}")
    names = ", ".join(str(path) for path in missing)
    if len(missing) == len(paths):
        raise unittest.SkipTest(f"private integration fixtures absent: {names}")
    if missing:
        raise AssertionError(f"private integration fixtures incomplete; missing: {names}")
