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


def _shortest_key(slug):
    """The last path segment a Quartz "shortest" match compares against, with
    a folder's own index.md standing in for its parent folder name (so
    [[armada]] can resolve to locations/armada/index.md)."""
    parts = slug.split("/")
    if parts[-1] == "index" and len(parts) >= 2:
        return parts[-2]
    return parts[-1]


def resolve_target(target, slugs, slug_set):
    """Resolve an Obsidian wikilink target to a content slug exactly the way
    Quartz's markdownLinkResolution:"shortest" does (quartz/util/path.ts,
    transformLink): a UNIQUE last-segment match wins; otherwise (zero or two-
    plus matches) the target is taken as an absolute root-relative slug and
    resolves only if that slug (or that folder's index) actually exists.

    This is why a bilingual wiki's [[pt/world]] and a nested [[gazetteer/
    marrogate]] resolve (absolute path hits a real page) while a bare
    [[marrogate]] that matches two files does NOT (two matches -> absolute
    /marrogate -> no such page). A trailing slash marks a folder link, which
    Quartz resolves ONLY to that folder's index. Returns the resolved slug, or
    None if Quartz would leave the link dangling.

    Case-SENSITIVE, matching Quartz's sluggify (which never lowercases). The
    grounding gate's twin resolve_slug lowercases instead, deliberately: that
    gate keys everything lowercase and errs toward grounding (a genuinely
    broken link is this gate's job to flag, not that one's)."""
    raw = target.split("#", 1)[0].strip()
    is_folder = raw.endswith("/")
    canonical = raw.strip("/")
    if not canonical:
        return None
    if is_folder:
        # [[world/]] -> Quartz emits /world/ and serves only world/index.
        return f"{canonical}/index" if f"{canonical}/index" in slug_set else None
    matches = [s for s in slugs if _shortest_key(s) == canonical]
    if len(matches) == 1:
        return matches[0]
    if canonical in slug_set:
        return canonical
    if f"{canonical}/index" in slug_set:
        return f"{canonical}/index"
    return None


def find_broken(slugs, slug_set):
    broken = []
    for md_file in sorted(CONTENT_DIR.rglob("*.md")):
        for lineno, line in enumerate(md_file.read_text().splitlines(), 1):
            for match in LINK_RE.finditer(line):
                if is_embed(line, match.start()):
                    continue
                target = match.group(1).strip()
                if target and resolve_target(target, slugs, slug_set) is None:
                    broken.append((md_file, lineno, target))
    return broken


def fix_file(md_file, slugs, slug_set):
    lines = md_file.read_text().splitlines()
    new_lines = []
    changes = []
    for lineno, line in enumerate(lines, 1):
        toc_match = TOC_LINE_RE.match(line)
        if toc_match and resolve_target(toc_match.group(2).strip(), slugs, slug_set) is None:
            changes.append((lineno, "deleted line", line.strip()))
            continue  # drop the whole line

        def replace(m):
            if is_embed(line, m.start()):
                return m.group(0)
            target = m.group(1).strip()
            if resolve_target(target, slugs, slug_set) is not None:
                return m.group(0)
            display = (m.group(3) or target).strip()
            changes.append((lineno, f"de-linked to plain text: {display!r}", line.strip()))
            return display

        new_lines.append(LINK_RE.sub(replace, line))
    md_file.write_text("\n".join(new_lines) + "\n")
    return changes


def page_slugs():
    """Every page's full root-relative slug (POSIX, no .md), plus a set for
    fast membership. A target resolves against these the way Quartz does; see
    resolve_target. Full slugs (not just basenames) are what let [[pt/world]]
    and [[gazetteer/marrogate]] resolve instead of being false-flagged."""
    slugs = sorted(
        p.relative_to(CONTENT_DIR).with_suffix("").as_posix()
        for p in CONTENT_DIR.rglob("*.md")
    )
    return slugs, set(slugs)


def main():
    fix = "--fix" in sys.argv
    slugs, slug_set = page_slugs()
    broken = find_broken(slugs, slug_set)

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
        for lineno, action, original in fix_file(md_file, slugs, slug_set):
            print(f"  {md_file.relative_to(CONTENT_DIR)}:{lineno} -> {action}")
            print(f"      was: {original}")

    remaining = find_broken(slugs, slug_set)
    if remaining:
        print(f"\n{len(remaining)} broken wikilink(s) could not be auto-fixed, needs a manual look:")
        for md_file, lineno, target in remaining:
            print(f"  {md_file.relative_to(CONTENT_DIR)}:{lineno} -> [[{target}]]")
    else:
        print("\nAll broken wikilinks resolved.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
