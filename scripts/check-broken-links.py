#!/usr/bin/env python3
"""
Scan content/*.md for Obsidian-style wikilinks ([[target]] or [[target|Display]])
pointing at a page that doesn't exist in content/. Quartz itself renders these
identically to working links (same class, no visual difference), so this is the
only way to know before a player finds one by clicking a dead end.

Default mode just reports. Pass --fix to also repair what it finds:
  - A markdown list line that's entirely "- [[target|Display]]" or
    "- [[target|Display]]: some description" (a TOC-style entry whose whole
    point was describing that now-gone page) gets deleted outright.
  - Any other occurrence (an inline mention inside a sentence) gets de-linked
    in place: "[[target|Display]]" becomes plain "Display" (or "target" if
    there was no pipe), so the surrounding sentence stays intact.

--fix is a mechanical, no-judgment repair: it guarantees no dead link survives,
it does NOT rewrite prose or decide whether a whole paragraph built around the
missing page still deserves to exist. That call still needs a human read.
"""
import re
import sys
from pathlib import Path

CONTENT_DIR = Path(__file__).resolve().parent.parent / "content"
# A wikilink inside a markdown table escapes its pipe as \| (Quartz renders
# that correctly), so the target group must not swallow the backslash and the
# separator must accept both | and \|.
LINK_RE = re.compile(r"\[\[([^\]|#\\]+)(\\?\|([^\]]+))?\]\]")
TOC_LINE_RE = re.compile(r"^(\s*-\s*)\[\[([^\]|#\\]+)(\\?\|([^\]]+))?\]\](\s*:.*)?\s*$")


def is_embed(line, match_start):
    """A leading `!` turns [[...]] into an embed (an image, not a page
    link) - Quartz resolves those against asset files, not content/*.md,
    so they must never be treated as broken links just because their
    target isn't a page. `![[hesper.jpg|320]]` is a real, working embed
    even though there's no hesper.jpg.md anywhere."""
    return match_start > 0 and line[match_start - 1] == "!"


def find_broken(existing):
    broken = []
    for md_file in sorted(CONTENT_DIR.rglob("*.md")):
        for lineno, line in enumerate(md_file.read_text().splitlines(), 1):
            for match in LINK_RE.finditer(line):
                if is_embed(line, match.start()):
                    continue
                target = match.group(1).strip()
                if target and target not in existing:
                    broken.append((md_file, lineno, target))
    return broken


def fix_file(md_file, existing):
    lines = md_file.read_text().splitlines()
    new_lines = []
    changes = []
    for lineno, line in enumerate(lines, 1):
        toc_match = TOC_LINE_RE.match(line)
        if toc_match and toc_match.group(2).strip() not in existing:
            changes.append((lineno, "deleted line", line.strip()))
            continue  # drop the whole line

        def replace(m):
            if is_embed(line, m.start()):
                return m.group(0)
            target = m.group(1).strip()
            if target in existing:
                return m.group(0)
            display = (m.group(3) or target).strip()
            changes.append((lineno, f"de-linked to plain text: {display!r}", line.strip()))
            return display

        new_lines.append(LINK_RE.sub(replace, line))
    md_file.write_text("\n".join(new_lines) + "\n")
    return changes


def existing_targets():
    """Every wikilink target Quartz's resolver would consider satisfied:
    a page's own filename, plus (matching the patched "shortest" resolution
    strategy in quartz/util/path.ts) a folder's name for its own index.md."""
    targets = set()
    for p in CONTENT_DIR.rglob("*.md"):
        targets.add(p.stem)
        if p.stem == "index":
            targets.add(p.parent.name)
    return targets


def main():
    fix = "--fix" in sys.argv
    existing = existing_targets()
    broken = find_broken(existing)

    if not broken:
        print("No broken wikilinks found.")
        return 0

    if not fix:
        print(f"Found {len(broken)} broken wikilink(s):\n")
        for md_file, lineno, target in broken:
            print(f"  {md_file.relative_to(CONTENT_DIR)}:{lineno} -> [[{target}]]")
        return 0

    affected_files = sorted({md_file for md_file, _, _ in broken})
    print(f"Found {len(broken)} broken wikilink(s) across {len(affected_files)} file(s), fixing:\n")
    for md_file in affected_files:
        for lineno, action, original in fix_file(md_file, existing):
            print(f"  {md_file.relative_to(CONTENT_DIR)}:{lineno} -> {action}")
            print(f"      was: {original}")

    remaining = find_broken(existing)
    if remaining:
        print(f"\n{len(remaining)} broken wikilink(s) could not be auto-fixed, needs a manual look:")
        for md_file, lineno, target in remaining:
            print(f"  {md_file.relative_to(CONTENT_DIR)}:{lineno} -> [[{target}]]")
    else:
        print("\nAll broken wikilinks resolved.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
