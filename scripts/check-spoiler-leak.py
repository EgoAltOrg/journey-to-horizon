#!/usr/bin/env python3
"""
Spoiler-leak gate for the published player-facing wiki.

WHY THIS EXISTS: on 2026-07-18 an author-side note reading "the truth is
otherwise, and is GM-only" reached the live player site inside a public bullet
on a magic page. It was NOT inside a [!gm-only] callout, so the sync's
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
    exact (file, matched-phrase) pair is cleared in the wiki's
    spoiler-leak-allowlist.json with a human-written reason. That file sits in
    scripts/, or in the WIKI_CONFIG_DIR folder for a wiki whose config stays
    out of the public repo (see wiki_config.py); never in both.

Exit 1 on any finding, no --fix: clearing a spoiler is a human judgment call.
Run from the repo root: python3 scripts/check-spoiler-leak.py
"""
import json
import re
import sys
from pathlib import Path

from wiki_config import config_path

CONTENT = Path(__file__).resolve().parent.parent / "content"
ALLOWLIST_PATH = config_path("spoiler-leak-allowlist.json")

# Author-side terminology and secret-existence markers. Zero legitimate use in
# player-facing prose on ANY wiki, so these are never allowlistable and never
# reclassifiable: "gm-only"/"gm-notes"/"[!gm" are the real leak vectors (an
# author note that escaped its callout). Fix the source instead.
TIER1_AUTHOR_MARKERS = [
    r"\bgm[-\s]?only\b",
    r"\bgm[-\s]?notes?\b",
    r"\[!\s*gm",
    r"\bthe truth is otherwise\b",
    r"\bnot for (the )?players\b",
    r"\bdo\s?n[’']?t reveal\b",
    r"\breveal(ed)? to (the )?players\b",
    # Hyphenated jargon spellings only: the spaced forms are ordinary English
    # ("out of character for the duke") and live in Tier 2.
    r"\bin-fiction\b",
    r"\bout-of-character\b",
    r"\bdesign pass\b",
]

# The GM named as a role/person. On a single-GM, secret-heavy wiki (Althas) this
# in player prose reads as author voice, so it defaults to Tier 1. On an open
# table whose premise IS a rotating GM pool (Journey to Horizon), the role word
# is ordinary player vocabulary ("each session has a different GM"). A wiki opts
# these OUT of Tier 1 by setting "gm_role_is_player_vocabulary": true in its
# spoiler-leak-allowlist.json; that flag NEVER touches the author markers above.
TIER1_GM_ROLE = [
    r"\bgm\b",
    r"\bgamemaster\b",
    r"\bgame master\b",
    r"\bdungeon master\b",
]

# Object slot for the perception-framing patterns below: a pronoun or a short
# determiner phrase ("the wear", "these duels").
_OBJ = r"(?:him|her|them|it|(?:the|this|that|these|those|his|her|their|its) \w+)"

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
    # back behind a barrier. Caught live on 2026-08-07 in public magic prose.
    # Tight enough not to hit an in-world spell line such as "Wall raises it as
    # a barrier".
    r"\bkeeps something worse\b",
    r"\bbehind a barrier\b",
    r"\bprison wall\b",
    # Perception-framing leak class: a line about how people *see* someone
    # implies the truth is otherwise with no trigger word ("most read the scars
    # on him as the marks of an honest trade"). Caught 2026-09-27 on a public NPC
    # page, after it had been live since the 2026-09-26 publish. That first
    # version hard-coded seven subjects (most, many, others, ...), so six live
    # lines found 2026-09-30 slipped through (shapes like "the faithful read it
    # as", "a match the city reads as", "passes off as", "as the court
    # believes", "in the eyes of", "the rest is held"). The "as" forms are
    # therefore subject-agnostic too, each kept tight in its own way:
    #   - the subject-anchored original (any verb, any object) stays first, so
    #     its matches keep their old phrase;
    #   - read/see/mistake + a real object, any subject;
    #   - take + a bare pronoun directly before "as" ("took him as"), so
    #     succession prose ("took the throne as regent", "took her place as
    #     head") does not flag;
    #   - a fronted object ("a match the city reads as", "who reads as"),
    #     where "reads as follows/such/well" is prose; "as well-born" is not.
    r"\b(?:(?:most|many|others|people|everyone|all|few) (?:read|reads|take|takes|took|see|sees|saw|mistake|mistakes|mistook) "
    + _OBJ
    + r"(?: \w+){0,4} as\b|(?:read|reads|see|sees|saw|mistake|mistakes|mistook) "
    + _OBJ
    + r"(?: \w+){0,4} as\b|(?:take|takes|took) (?:him|her|them|it) as\b"
    + r"|(?:who reads?|reads|sees) as\b(?! (?:follows|such|well(?!-))\b))",
    # "for" forms: the subject-anchored original, plus "take him for" and
    # "mistook <someone> for" with any subject. Read/see + "for" stays
    # subject-anchored: "see that page for" and "read the ground for" are prose.
    # With any subject, "took it for granted" is an idiom, not framing; with a
    # perceiver subject ("Most took it for granted that...") it stays flagged.
    r"\b(?:(?:most|many|others|people|everyone|all|few) (?:read|reads|take|takes|took|see|sees|saw|mistake|mistakes|mistook) "
    + _OBJ
    + r"(?: \w+){0,4} for\b|(?:take|takes|took) (?:him|her|them|it) for\b(?! granted\b)|(?:mistake|mistakes|mistook) "
    + _OBJ
    + r"(?: \w+){0,4} for\b)",
    r"\bpass(es|ed)? for\b",
    r"\bpass(es|ed|ing)? (\w+ )?off as\b",
    r"\bas (\w+ ){1,2}believe[sd]?\b",
    r"\bas (\w+ ){1,2}presents? (it|them|him|her|itself|himself|herself|themselves)\b",
    r"\bby all appearances\b",
    r"\b(is|was|are|were) (taken|mistaken) (for|to be)\b",
    r"\bin the eyes of\b",
    # Secret-existence hints: the line says outright that more is known than
    # is shown.
    r"\bpublicly (known|presents?|held|claimed)\b",
    r"\bnever (said|claimed|told) otherwise\b",
    r"\bthe rest is held\b",
    # Workshop vocabulary that should not survive into finished player prose.
    r"\bhomebrew",
    r"\bplaceholder",
    # Spaced forms of Tier 1 jargon: ordinary English too, so allowlistable.
    r"\bout of character\b",
    r"\bin fiction\b",
]

TIER1_AUTHOR_RE = [re.compile(p, re.IGNORECASE) for p in TIER1_AUTHOR_MARKERS]
TIER1_GM_ROLE_RE = [re.compile(p, re.IGNORECASE) for p in TIER1_GM_ROLE]
# Default (strict): author markers + GM role, i.e. pre-config behavior.
TIER1_STRICT_RE = TIER1_AUTHOR_RE + TIER1_GM_ROLE_RE
TIER2_RE = [re.compile(p, re.IGNORECASE) for p in TIER2]
FRONTMATTER_RE = re.compile(r"^---\n.*?\n---\n?", re.DOTALL)


def load_allowlist():
    if not ALLOWLIST_PATH.exists():
        return {}
    return json.loads(ALLOWLIST_PATH.read_text())


def scan_text(text, tier1_res=None):
    """Return (tier1_hits, tier2_hits): lists of (line_no, matched_phrase).
    tier1_res defaults to the strict set (author markers + GM role); main()
    passes the active set once it has read the per-wiki role-term flag."""
    if tier1_res is None:
        tier1_res = TIER1_STRICT_RE
    t1, t2 = [], []
    for i, line in enumerate(text.splitlines(), 1):
        for rx in tier1_res:
            for m in rx.finditer(line):
                t1.append((i, m.group(0).lower()))
        for rx in TIER2_RE:
            for m in rx.finditer(line):
                t2.append((i, m.group(0).lower()))
    return t1, t2


def tier1_for(data):
    """The active Tier 1 set for one wiki's allowlist data."""
    # Per-wiki spoiler strictness: an open table (rotating GMs) opts the GM ROLE
    # terms out of Tier 1; the author markers stay Tier 1 unconditionally.
    role_is_vocab = bool(data.get("gm_role_is_player_vocabulary", False))
    tier1_res = TIER1_AUTHOR_RE if role_is_vocab else TIER1_STRICT_RE
    # Per-wiki author terms: the setting's own internal names that never appear
    # in player prose (Althas lists its working name for the year-end holidays).
    # They join Tier 1, so they are never allowlistable either.
    return tier1_res + [re.compile(p, re.IGNORECASE) for p in data.get("extra_author_terms", [])]


def main():
    data = load_allowlist()
    allow = data.get("pages", {})
    tier1_res = tier1_for(data)
    findings = []
    for md in sorted(CONTENT.rglob("*.md")):
        if ".obsidian" in md.parts:
            continue
        rel = str(md.relative_to(CONTENT))
        text = md.read_text()
        # Frontmatter can legitimately hold nothing secret, but scan the whole
        # file anyway: a leaked key would matter too. (Kept simple: scan all.)
        t1, t2 = scan_text(text, tier1_res)
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
            f"Tier 2 false positive, add it to {ALLOWLIST_PATH} "
            "with a reason. Tier 1 hits are never allowlisted."
        )
        return 1
    print("check-spoiler-leak: OK (no author terminology or unexplained secret-signaling in content/)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
