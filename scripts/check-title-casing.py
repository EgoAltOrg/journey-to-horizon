#!/usr/bin/env python3
"""
Guard against a recurring bug: a proper-noun page (e.g. "The Ones Below")
being linked with lowercased display text ("the ones below") so it renders
wrong on the public site.

Quartz renders a wikilink's display text verbatim, so `[[the-ones-below|the
ones below]]` shows "the ones below" even though the page's canonical title
is "The Ones Below". A bare `[[the-ones-below]]` is worse: it renders the raw
slug. This has been fixed by hand more than once and kept coming back, so it
now has a mechanical gate that runs in the publish flow.

What it flags, per wikilink in content/:
  - a *bare* link (`[[slug]]`, no pipe) whose target title has any capital
    letter (i.e. a proper noun): it will render lowercase, add a pipe.
  - a *piped* link whose display text is the SAME phrase as the target's
    title but cased differently in a significant (non-article) word:
    "the ones below" vs title "The Ones Below" is flagged; "the Ones Below"
    is fine (a lowercase leading article is allowed mid-sentence); a
    genuinely different alias like "House Voldis's" for Voldaen is NOT
    flagged (different words, not a casing slip).

Exit status is nonzero if anything is flagged, so the publish step can stop.
Run from the repo root: python3 scripts/check-title-casing.py
"""
import re
import sys
from pathlib import Path

CONTENT = Path(__file__).resolve().parent.parent / "content"

# Titles that are also ordinary common nouns and are correctly lowercased
# mid-sentence ("a flock of faeries"), matching how their own page writes them.
# The proper-noun casing gate is skipped for these slugs.
COMMON_NOUN_SLUGS = {"aetheris", "elves"}
TITLE_RE = re.compile(r"^title:\s*(.+?)\s*$", re.MULTILINE)
# [[target|display]] or [[target]] ; target may carry a path and/or #anchor
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]+))?\]\]")


def strip_the(s):
    return re.sub(r"^the\s+", "", s, flags=re.IGNORECASE)


def slug_of(path):
    # a folder's own index.md answers to the folder name (armada, jesthaen…)
    if path.name == "index.md" and path.parent != CONTENT:
        return path.parent.name
    return path.stem


def build_titles():
    titles = {}
    for md in CONTENT.rglob("*.md"):
        if ".obsidian" in md.parts:
            continue
        m = TITLE_RE.search(md.read_text())
        if m:
            titles[slug_of(md)] = m.group(1).strip().strip('"')
    return titles


def main():
    titles = build_titles()
    flags = []
    for md in sorted(CONTENT.rglob("*.md")):
        if ".obsidian" in md.parts:
            continue
        for i, line in enumerate(md.read_text().splitlines(), 1):
            for m in WIKILINK_RE.finditer(line):
                target_raw, display = m.group(1), m.group(2)
                slug = target_raw.strip().split("/")[-1].strip()
                title = titles.get(slug)
                if not title or slug in COMMON_NOUN_SLUGS:
                    continue  # unknown/cross-project target, or a common noun: not our concern here
                rel = md.relative_to(CONTENT)
                if display is None:
                    if title != title.lower():  # proper noun rendered as raw slug
                        flags.append((rel, i, f"bare [[{slug}]] renders lowercase; use [[{slug}|{title}]]"))
                    continue
                display = display.strip()
                if strip_the(display).lower() == strip_the(title).lower() and \
                   strip_the(display) != strip_the(title):
                    flags.append((rel, i, f'"{display}" should match title casing "{title}" (a lowercase leading "the" is fine)'))

    if flags:
        print(f"Found {len(flags)} title-casing issue(s):\n")
        for rel, ln, msg in flags:
            print(f"  {rel}:{ln} -> {msg}")
        return 1
    print("No title-casing issues found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
