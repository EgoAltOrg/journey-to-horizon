#!/usr/bin/env python3
"""
Spoiler-leak gate for the published player-facing wiki.

WHY THIS EXISTS: on 2026-07-18 an author-side note reading "the truth is
otherwise, and is GM-only" reached the live player site inside a public bullet
on magic/miracles.md. It was NOT inside a [!gm-only] callout, so the sync's
strip could not catch it, and a human diff review missed the parenthetical.
That class of leak (author terminology or secret-existence hints written into
public prose) is catastrophic for a GM: it tells players a secret exists and
where to dig. This gate makes that class of leak un-shippable.

WHAT IT SCANS: the GENERATED content/ folder, i.e. exactly what players see
AFTER the gm-only/gm-notes strip. Anything matched here has, by definition,
escaped the callout strip. Scanning the Ontos source instead would false-flag
every legitimate [!gm-only] callout, so this must run on content/.

TWO TIERS:
  - TIER 1 (author terminology): words that should NEVER appear in player
    prose ("gm-only", "gm-notes", a bare "GM", "the truth is otherwise", etc.).
    Always a hard finding. NOT allowlistable, by design.
  - TIER 2 (secret-signaling phrases): language that MIGHT signal a hidden
    secret ("secretly", "in reality", "not public", ...). A finding unless the
    exact (file, matched-phrase) pair is cleared in
    scripts/spoiler-leak-allowlist.json with a human-written reason.

Exit 1 on any finding, no --fix: clearing a spoiler is a human judgment call.
Run from the repo root: python3 scripts/check-spoiler-leak.py
"""
import json
import re
import sys
from pathlib import Path

CONTENT = Path(__file__).resolve().parent.parent / "content"
ALLOWLIST_PATH = Path(__file__).resolve().parent / "spoiler-leak-allowlist.json"

# Author-side terminology. Zero legitimate use in player-facing prose, so these
# are never allowlistable: fix the source instead.
TIER1 = [
    r"\bgm[-\s]?only\b",
    r"\bgm[-\s]?notes?\b",
    r"\bgm\b",
    r"\[!\s*gm",
    r"\bthe truth is otherwise\b",
    r"\bnot for (the )?players\b",
    r"\bdo\s?n[’']?t reveal\b",
    r"\breveal(ed)? to (the )?players\b",
    r"\bgamemaster\b",
    r"\bgame master\b",
    r"\bdungeon master\b",
]

# Secret-signaling phrases. Real leaks look like these, but so does some
# legitimate in-world prose ("a hole in reality"), so each hit is cleared only
# by an explicit allowlist entry with a reason.
TIER2 = [
    r"\bin truth\b",
    r"\b(the )?real truth\b",
    r"\bhidden truth\b",
    r"\bsecretly\b",
    r"\bin secret\b",
    r"\bthe secret\b",
    r"\bnot (yet )?publicly\b",
    r"\bnot (yet )?public\b",
    r"\bunknown to\b",
    r"\bcover story\b",
    r"\bposing as\b",
    r"\bin reality\b",
    r"\breally (is|a|an|the)\b",
    r"\bthe real reason\b",
    r"\bplayers (will|should|know|knew|do|don'?t|won'?t|are|have|had|must|might|need)\b",
    r"\bforeshadow",
    r"\bspoiler",
    r"\bin disguise\b",
    r"\bpretend(s|ing|ed)?\b",
    # Barrier/prison-wall leak class: a secret that a dangerous thing is held
    # back behind a barrier (Codex's true source, the Ones Below seal). Caught
    # live on 2026-08-07 in public codex-magic prose. Tight enough not to hit the
    # in-world seal-grammar "Wall raises it as a barrier" dagger.
    r"\bkeeps something worse\b",
    r"\bbehind a barrier\b",
    r"\bprison wall\b",
]

TIER1_RE = [re.compile(p, re.IGNORECASE) for p in TIER1]
TIER2_RE = [re.compile(p, re.IGNORECASE) for p in TIER2]
FRONTMATTER_RE = re.compile(r"^---\n.*?\n---\n?", re.DOTALL)


def load_allowlist():
    if not ALLOWLIST_PATH.exists():
        return {}
    data = json.loads(ALLOWLIST_PATH.read_text())
    return data.get("pages", {})


def scan_text(text):
    """Return (tier1_hits, tier2_hits): lists of (line_no, matched_phrase)."""
    t1, t2 = [], []
    for i, line in enumerate(text.splitlines(), 1):
        for rx in TIER1_RE:
            for m in rx.finditer(line):
                t1.append((i, m.group(0).lower()))
        for rx in TIER2_RE:
            for m in rx.finditer(line):
                t2.append((i, m.group(0).lower()))
    return t1, t2


def main():
    allow = load_allowlist()
    findings = []
    for md in sorted(CONTENT.rglob("*.md")):
        if ".obsidian" in md.parts:
            continue
        rel = str(md.relative_to(CONTENT))
        text = md.read_text()
        # Frontmatter can legitimately hold nothing secret, but scan the whole
        # file anyway: a leaked key would matter too. (Kept simple: scan all.)
        t1, t2 = scan_text(text)
        for ln, phrase in t1:
            findings.append((rel, ln, phrase, "author-terminology (Tier 1, not allowlistable)"))
        page_allow = {k.lower() for k in allow.get(rel, {})}
        for ln, phrase in t2:
            if phrase in page_allow:
                continue
            findings.append((rel, ln, phrase, "secret-signaling (Tier 2; allowlist if legitimate)"))

    if findings:
        print(f"check-spoiler-leak: {len(findings)} potential leak(s) in published content/:\n")
        for rel, ln, phrase, why in findings:
            print(f"  {rel}:{ln} -> {phrase!r}  [{why}]")
        print(
            "\nEach must be resolved before publishing: fix the Ontos source "
            "(move author notes into a [!gm-only]/[!gm-notes] callout), or, for a "
            "Tier 2 false positive, add it to scripts/spoiler-leak-allowlist.json "
            "with a reason. Tier 1 hits are never allowlisted."
        )
        return 1
    print("check-spoiler-leak: OK (no author terminology or unexplained secret-signaling in content/)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
