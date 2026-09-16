#!/usr/bin/env python3
"""Offline tests for the Task-5 Gate-1 trace stub (analysis only).

These prove the stub is PASSIVE and captures the spec'd values in the model.
They do NOT prove flash safety; see docs/atlas-shell-usb-detach-trace.md for the
residual-risk assessment and why model-passivity is necessary-but-insufficient.

Run:
    python -B -m unittest -v tools/garmin-firmware/tests/test_emulate_atlas_shell_trace.py
"""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "atlas_shell_trace"))

import trace_stubs as ts  # noqa: E402
from emulate_atlas_shell_trace import emulate_gate1  # noqa: E402

# thread context and two modelled exception contexts
CONTEXTS = [
    dict(tcb=0x1FFCA000, owner=0x1FFCA000, recursion=0, ipsr=0x000, head=0),
    dict(tcb=0x1FFCA000, owner=0x00000000, recursion=1, ipsr=0x00B, head=5),
    dict(tcb=0x20001234, owner=0x20005678, recursion=3, ipsr=0x0F0, head=63),
]


class BranchEncoderTest(unittest.TestCase):
    def test_bw_reproduces_real_image_encoding(self):
        # The displaced instruction at 0x20A8A is b.w 0x874C = e7 f7 5f be.
        self.assertEqual(
            ts._bw(ts.HOOK_GATE1_VA, ts.UNLOCK_VA), bytes.fromhex("e7f75fbe")
        )

    def test_stub_fully_decodes(self):
        asm = ts.gate1_stub()
        lines = ts.verify_stub(asm)  # raises if any halfword is undefined
        self.assertTrue(any("b.w" in ln and "0x874c" in ln for ln in lines))
        self.assertLessEqual(len(asm.code), 0x800)  # fits the 2 KiB cave


class RedBaselineTest(unittest.TestCase):
    """Prove the correctness assertions are non-vacuous."""

    def test_null_stub_captures_nothing(self):
        r = emulate_gate1(**CONTEXTS[0], stub_factory=ts.gate1_stub_null)
        self.assertFalse(r["record_correct"])
        self.assertFalse(r["head_advanced"])
        # it still reaches the displaced unlock (it is just the branch)
        self.assertTrue(r["reached_unlock"])


class Gate1CaptureTest(unittest.TestCase):
    def test_captures_all_four_values(self):
        for ctx in CONTEXTS:
            with self.subTest(ctx=ctx):
                r = emulate_gate1(**ctx)
                self.assertTrue(r["record_correct"], r["record"])
                self.assertEqual(r["record"]["captured_tcb"], ctx["tcb"])
                self.assertEqual(r["record"]["captured_owner"], ctx["owner"])
                self.assertEqual(
                    r["record"]["captured_recursion"], ctx["recursion"] & 0xFFFF
                )
                self.assertEqual(r["record"]["captured_ipsr"], ctx["ipsr"] & 0x1FF)
                self.assertTrue(r["head_advanced"])


class PassivityTest(unittest.TestCase):
    def test_never_reaches_forbidden_primitive(self):
        for ctx in CONTEXTS:
            with self.subTest(ctx=ctx):
                r = emulate_gate1(**ctx)
                self.assertIsNone(r["violation"])
                self.assertIsNone(r["unmapped"])
                self.assertIsNone(r["uc_error"])
                self.assertTrue(r["reached_unlock"])

    def test_writes_confined_to_stack_and_ring(self):
        for ctx in CONTEXTS:
            with self.subTest(ctx=ctx):
                r = emulate_gate1(**ctx)
                self.assertTrue(r["writes_confined"], r["writes"])
                self.assertEqual(r["ring_write_count"], 5)  # 4 record words + head
                self.assertEqual(r["stack_write_count"], 4)  # push {r1,r2,r3,r12}

    def test_preserves_r0_lr_sp_and_restores_scratch(self):
        for ctx in CONTEXTS:
            with self.subTest(ctx=ctx):
                r = emulate_gate1(**ctx)
                self.assertTrue(r["r0_preserved"], "r0 (USB mutex arg) clobbered")
                self.assertTrue(r["lr_preserved"], "lr (scheduler return) clobbered")
                self.assertTrue(r["sp_balanced"], "stack imbalance")
                self.assertTrue(r["scratch_restored"], "scratch not restored")


class ContextAgnosticTest(unittest.TestCase):
    def test_thread_and_exception_context_behave_identically(self):
        base = dict(tcb=0x1FFCB000, owner=0x1FFCB000, recursion=2, head=10)
        thread = emulate_gate1(**base, ipsr=0x000)
        exc = emulate_gate1(**base, ipsr=0x030)  # some IRQ number
        # identical control flow, register discipline, footprint; only the
        # recorded IPSR field differs.
        for key in (
            "reached_unlock",
            "violation",
            "r0_preserved",
            "lr_preserved",
            "sp_balanced",
            "scratch_restored",
            "writes_confined",
            "ring_write_count",
            "stack_write_count",
            "instr_count",
        ):
            self.assertEqual(thread[key], exc[key], key)
        self.assertEqual(thread["record"]["captured_ipsr"], 0x000)
        self.assertEqual(exc["record"]["captured_ipsr"], 0x030)


if __name__ == "__main__":
    unittest.main()
