#!/usr/bin/env python3
"""Unit tests for check-spoiler-leak.py's scanner.
Run: python3 scripts/test-check-spoiler-leak.py"""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "check_spoiler_leak", Path(__file__).resolve().parent / "check-spoiler-leak.py"
)
csl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(csl)


def test_catches_the_real_leak():
    # The exact 2026-07-18 leak string must be caught (Tier 1).
    leak = "said to let its bearer hold multiple Miracles (the truth is otherwise, and is GM-only)."
    t1, t2 = csl.scan_text(leak)
    phrases = {p for _, p in t1}
    assert "gm-only" in phrases, "must catch 'GM-only' author terminology"
    assert "the truth is otherwise" in phrases, "must catch 'the truth is otherwise'"


def test_tier1_gm_terms():
    for s in ["This is GM-only.", "> [!gm-notes]", "a note for the GM here", "GM notes below"]:
        t1, _ = csl.scan_text(s)
        assert t1, f"expected a Tier 1 hit in: {s!r}"


def test_tier2_secret_signals():
    for s in ["He is secretly a traitor.", "not yet public knowledge", "posing as a merchant"]:
        _, t2 = csl.scan_text(s)
        assert t2, f"expected a Tier 2 hit in: {s!r}"


def test_clean_public_prose_passes():
    clean = (
        "The Holy See governs the faith from Hilltop and fields the Parish of "
        "Inquisition as its investigative arm. House Voldis rules Voldaen."
    )
    t1, t2 = csl.scan_text(clean)
    assert not t1 and not t2, f"clean prose should not flag: {t1} {t2}"


def test_in_reality_is_tier2_not_tier1():
    # 'a hole in reality' is legit and only Tier 2 (allowlistable), never Tier 1.
    t1, t2 = csl.scan_text("Codex tears a small hole in reality.")
    assert not t1, "'in reality' must not be Tier 1"
    assert any(p == "in reality" for _, p in t2), "'in reality' should be a Tier 2 hit"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"  PASS {name}")
    print("All check-spoiler-leak tests passed.")
