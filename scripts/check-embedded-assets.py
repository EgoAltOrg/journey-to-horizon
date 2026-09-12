#!/usr/bin/env python3
"""Verify every image/media embed in content/ resolves to a real asset file.

The gap this closes: `check-broken-links.py` deliberately SKIPS every embed
(a leading `!` on `[[...]]`), because embeds resolve against asset files, not
`content/*.md` pages, so they must never be flagged as broken page links. But
that means an embed pointing at a MISSING asset (`![[the-mad-king-full-body.webp|320]]`
when no such file was ever copied into `content/assets/`) sailed through every
gate silently: the markdown looked right, all checks passed, and the image just
didn't render on the live site. That is exactly how Valerion Voldis's second
Depictions image went missing (2026-08-18).

Assets are NOT copied by `sync-from-ontos.py`; they live only in `content/`
(root CLAUDE.md rule 26) and are placed by hand. So a new body embed syncs as
text while its file is easy to forget. This gate is the mechanical backstop:
report-only, exits non-zero on any missing asset, no `--fix` (the fix is
copying a binary in, never a machine edit). Wire it into the publish pipeline's
mechanical-gates block alongside the other check-*.py scripts.

Resolution mirrors Quartz: an embed target is matched by basename against the
media files present anywhere under content/ (assets are flat in content/assets/,
but a basename match is robust to that layout changing)."""

import re
import sys
from pathlib import Path

CONTENT_DIR = Path(__file__).resolve().parent.parent / "content"

# Extensions Quartz treats as a media embed rather than a page transclusion.
MEDIA_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".avif",
    ".mp4", ".webm", ".mov", ".mp3", ".wav", ".ogg", ".pdf",
}

# `![[target|size]]` or `![[target]]` wikilink embed.
WIKI_EMBED_RE = re.compile(r"!\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]")
# `![alt](path)` markdown embed.
MD_EMBED_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")


def has_media_ext(target):
    return Path(target).suffix.lower() in MEDIA_EXTS


def is_local(target):
    """Skip anything Quartz would fetch over the network rather than resolve
    against a local asset."""
    t = target.strip().lower()
    return not (t.startswith(("http://", "https://", "//", "data:", "mailto:")))


def available_assets():
    """Every media file under content/, indexed by basename (Quartz's
    shortest-path resolver matches an embed to a file by name)."""
    names = set()
    for p in CONTENT_DIR.rglob("*"):
        if p.is_file() and p.suffix.lower() in MEDIA_EXTS:
            names.add(p.name)
    return names


def embed_targets(line):
    """Every local media target referenced on one line, both embed syntaxes."""
    for m in WIKI_EMBED_RE.finditer(line):
        target = m.group(1).strip()
        if has_media_ext(target) and is_local(target):
            yield target
    for m in MD_EMBED_RE.finditer(line):
        target = m.group(1).strip().split()[0]  # drop an optional "title" suffix
        if has_media_ext(target) and is_local(target):
            yield target


def find_missing(assets):
    missing = []
    for md_file in sorted(CONTENT_DIR.rglob("*.md")):
        for lineno, line in enumerate(md_file.read_text().splitlines(), 1):
            for target in embed_targets(line):
                if Path(target).name not in assets:
                    missing.append((md_file, lineno, target))
    return missing


def main():
    assets = available_assets()
    missing = find_missing(assets)

    if not missing:
        print("All embedded assets resolve.")
        return 0

    print(f"Found {len(missing)} embed(s) pointing at a missing asset:\n")
    for md_file, lineno, target in missing:
        print(f"  {md_file.relative_to(CONTENT_DIR)}:{lineno} -> ![[{target}]]")
    print(
        "\nEach target must exist as a file under content/assets/. "
        "Copy the image in (assets are placed by hand, not synced)."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
