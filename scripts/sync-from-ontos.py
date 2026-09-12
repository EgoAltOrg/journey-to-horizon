#!/usr/bin/env python3
"""
Sync a wiki's player-facing content/ folder from its source pages in the Ontos
vault. This is the shared engine for every wiki created from the template; the
wiki-specific data (source dir, page map, titles, renames, skip-lists, infobox
schema) lives in sync_config.py, the one file each wiki edits.

Source pages are annotated with two Obsidian callout types: [!gm-only] for
in-world secrets not yet revealed to players (unwrapped by hand as the campaign
plays out) and [!gm-notes] for permanent author-side content (real-world
citations, planning notes) that never reaches players. This script reads each
mapped source page, strips both callout types entirely, trims frontmatter down
to `title:` plus the whitelisted typed-infobox fields (carrying forward any
existing marker:/submap:/image: presentation data already in the destination
file), drops the Sources/Last updated bookkeeping lines, and writes the result
into content/.

content/ is a generated build artifact from this point on: don't hand-edit files
this script writes, edit the Ontos source and re-run. This is a mechanical strip,
not a judgment call: always read `git diff content/` yourself before publishing.

A wiki may map a page to a folder's own index.md (so [[foo]] resolves to
locations/foo/index.md, keeping a folder and a page inside it from sharing a
name). That relies on a patched "shortest" link-resolution strategy in
quartz/util/path.ts and a matching patch in check-broken-links.py; keep both
patches if you use folder-is-the-page.
"""
import re
import sys
from pathlib import Path

# All wiki-specific data lives in sync_config.py (the one file a wiki edits).
# Add this script's own dir to the path so the import works whether run directly
# or loaded by a gate via importlib (e.g. check-related-pages-grounding.py).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from sync_config import (  # noqa: E402
    ONTOS_SETTING,
    TITLES,
    PAGE_MAP,
    RENAMES,
    NOT_YET_PUBLIC,
    CONTENT_ONLY,
    INFOBOX_KIND_FIELDS,
)

CONTENT_DIR = Path(__file__).resolve().parent.parent / "content"

CALLOUT_START_RE = re.compile(r"^>\s*\[!(gm-only|gm-notes)\]", re.IGNORECASE)
# Any callout opener, GM or public. Used to stop stripping at a *public* callout
# that follows a GM block, so it is never swallowed (e.g. a CC-BY attribution).
CALLOUT_ANY_START_RE = re.compile(r"^>\s*\[!", re.IGNORECASE)
HEADING_RE = re.compile(r"^#{1,6}\s")
FRONTMATTER_RE = re.compile(r"^---\n(.*?\n)---\n?", re.DOTALL)


def split_frontmatter(text):
    m = FRONTMATTER_RE.match(text)
    if not m:
        return "", text
    return m.group(1), text[m.end():]


def extract_frontmatter_block(frontmatter_text, key):
    """Capture a top-level frontmatter key plus all its indented continuation
    lines (including YAML comments inside the block), verbatim."""
    lines = frontmatter_text.splitlines()
    for idx, line in enumerate(lines):
        if line.startswith(f"{key}:"):
            block = [line]
            j = idx + 1
            while j < len(lines) and (lines[j][:1] in (" ", "\t") or lines[j].strip() == ""):
                block.append(lines[j])
                j += 1
            while block and block[-1].strip() == "":
                block.pop()
            return "\n".join(block)
    return None


def extract_marker_block(frontmatter_text):
    return extract_frontmatter_block(frontmatter_text, "marker")


def extract_submap_block(frontmatter_text):
    """A page's embedded local map (`submap:` block: image, caption, local
    pins) is presentation data with no equivalent in the GM's source, same
    category as `marker:` map-pin coordinates. Carry it forward from the
    existing destination file so re-syncs never wipe it."""
    return extract_frontmatter_block(frontmatter_text, "submap")


def extract_image_block(frontmatter_text):
    """A page's portrait filename (`image:` key, value = a bare asset filename
    resolving to content/assets/) is presentation data with no equivalent in
    the GM's source, same category as `marker:` and `submap:`. Carry it forward
    from the existing destination file so re-syncing text content never wipes
    it. The frontend Infobox component renders it at the top of the card."""
    return extract_frontmatter_block(frontmatter_text, "image")


CURRENT_DATE_RE = re.compile(r'^current-date:\s*"?([0-9]+-(?:0[1-9]|10|H)-[0-9]{2})"?\s*$', re.MULTILINE)


def extract_current_date(frontmatter_text):
    """Campaign-date passthrough for the Chronicle (specs/althas-chronicle-
    calendar-design.md): the manually-advanced current-date lives in the Ontos
    source frontmatter and must reach the published page's frontmatter, where
    ChronicleCalendar.tsx reads it. Format VR-MM-DD, zero-padded, H = holidays."""
    if not frontmatter_text:
        return None
    m = CURRENT_DATE_RE.search(frontmatter_text)
    return m.group(1) if m else None


def extract_infobox_fields(frontmatter_text):
    """Pull the typed infobox lines out of the GM's source frontmatter,
    verbatim. Only `kind:` plus the fields belonging to that declared kind
    pass; a page without a valid `kind:` passes nothing. Indented
    continuation lines (block-style YAML lists) travel with their key,
    mirroring extract_marker_block()."""
    lines = frontmatter_text.splitlines()
    kind = None
    for line in lines:
        m = re.match(r"""^kind:\s*["']?([a-z-]+)["']?\s*$""", line)
        if m:
            kind = m.group(1)
            break
    if kind not in INFOBOX_KIND_FIELDS:
        return []
    allowed = ("kind",) + INFOBOX_KIND_FIELDS[kind]
    out = []
    i, n = 0, len(lines)
    while i < n:
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):", lines[i])
        if m and m.group(1) in allowed:
            block = [lines[i]]
            j = i + 1
            while j < n and (lines[j][:1] in (" ", "\t") or lines[j].strip() == ""):
                block.append(lines[j])
                j += 1
            while block and block[-1].strip() == "":
                block.pop()
            out.extend(block)
            i = j
            continue
        i += 1
    return out


def strip_callouts(body):
    lines = body.splitlines()
    out = []
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        if CALLOUT_START_RE.match(line):
            i += 1
            while i < n:
                # A new *public* callout ends the strip: it must survive (a GM
                # block must never swallow the public callout that follows it).
                if CALLOUT_ANY_START_RE.match(lines[i]) and not CALLOUT_START_RE.match(lines[i]):
                    break
                if lines[i].startswith(">"):
                    i += 1
                    continue
                if lines[i].strip() == "":
                    j = i
                    while j < n and lines[j].strip() == "":
                        j += 1
                    # Only chain across a blank gap to another GM callout; stop at
                    # a public callout or ordinary content so both survive.
                    if j < n and CALLOUT_START_RE.match(lines[j]):
                        i = j
                        continue
                break
            continue
        out.append(line)
        i += 1
    return "\n".join(out)


def strip_meta_lines(body):
    out = []
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("**Sources**:") or s.startswith("**Last updated**:"):
            continue
        out.append(line)
    return "\n".join(out)


def drop_empty_headings(body):
    """Drop a heading whose entire subtree (down to the next heading of the
    same or higher level) has no surviving content. Subtree-aware: a section
    kept alive only by a non-empty subsection survives (a `## Beliefs` whose
    sole child is a `### The Sleepless Vigil` with prose), while a heading
    whose subsections are all empty after the gm-only strip is dropped along
    with them (a deep-secret character's `## Abilities` of only gm-only text)."""
    lines = body.splitlines()
    n = len(lines)
    levels = [0] * n
    for i, line in enumerate(lines):
        m = re.match(r"^(#{1,6})\s", line)
        if m:
            levels[i] = len(m.group(1))
    drop = [False] * n
    for i in range(n):
        level = levels[i]
        if not level:
            continue
        j = i + 1
        has_content = False
        while j < n and not (levels[j] and levels[j] <= level):
            if not levels[j]:
                s = lines[j].strip()
                if s and s != "---":
                    has_content = True
            j += 1
        if not has_content:
            drop[i] = True
    return "\n".join(line for i, line in enumerate(lines) if not drop[i])


def clean_blank_runs(text):
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


IMAGE_EMBED_RE = re.compile(r"^!\[[^\]]*\]\([^)]+\)\s*$|^!\[\[[^\]|]+(\|[^\]]+)?\]\]\s*$")


def strip_leading_image(body):
    """Drop a standalone image embed if it's the first non-blank line of the
    Ontos body, and capture an italic caption line immediately following it.
    Returns (body_without_image_and_caption, caption_or_None).

    Portraits live in the GM's source page too (so Lucas's own vault renders
    them), but frontend art is managed separately here: the filename lives in
    the content-side `image:` frontmatter key (carried forward by
    extract_image_block) and the Infobox renders it, with the author's caption
    beneath it via the `image_caption:` key (this function's second return
    value, derived from the source each sync so Ontos stays authoritative for
    the caption text). Left in the body, the source embed would double up with
    the infobox portrait and the caption would render as loose article text
    instead of under the image. Only the leading image and its immediately
    following caption are touched; inline images elsewhere are untouched."""
    lines = body.splitlines()
    idx = 0
    while idx < len(lines) and lines[idx].strip() == "":
        idx += 1
    if idx >= len(lines) or not IMAGE_EMBED_RE.match(lines[idx]):
        return body, None
    drop = {idx}
    caption = None
    j = idx + 1
    while j < len(lines) and lines[j].strip() == "":
        j += 1
    if j < len(lines):
        cap = lines[j].strip()
        # A single-italic line (*...*): not bold (**...**), not a "* " bullet.
        if (
            len(cap) >= 2
            and cap.startswith("*")
            and cap.endswith("*")
            and not cap.startswith("**")
            and not cap.startswith("* ")
        ):
            caption = cap.strip("*").strip()
            drop.add(j)
    new_lines = [line for k, line in enumerate(lines) if k not in drop]
    return "\n".join(new_lines), caption


def render(
    title, marker_block, body, image_block=None, infobox_lines=None, submap_block=None,
    alias_slugs=None, image_caption=None, current_date=None,
):
    fm_lines = ["---", f"title: {title}"]
    if alias_slugs:
        fm_lines.append("aliases:")
        fm_lines.extend(f"  - {slug}" for slug in alias_slugs)
    if infobox_lines:
        fm_lines.extend(infobox_lines)
    if current_date:
        fm_lines.append(f'current-date: "{current_date}"')
    if image_block:
        fm_lines.append(image_block)
        if image_caption:
            fm_lines.append(f'image_caption: "{image_caption.replace(chr(34), chr(92) + chr(34))}"')
    if marker_block:
        fm_lines.append(marker_block)
    if submap_block:
        fm_lines.append(submap_block)
    fm_lines.append("---")
    return "\n".join(fm_lines) + "\n\n" + body


def carry_forward_source(dest, dest_rel):
    """Return the file to read carried-forward presentation blocks (`image:`,
    `marker:`, `submap:`) from, or None if there's nothing to carry.

    Normally that's the destination itself (the re-sync case). But those blocks
    live ONLY in content/, never in the Ontos source (rule 26), so a page
    *rename* would silently drop them: the new destination path has no prior
    file to carry from. In that case fall back to the most-recent prior
    destination recorded in RENAMES, whose content/ file still holds the data.
    RENAMES lists old slugs oldest-first (newly-old slugs are appended), so the
    most-recent prior destination is the last surviving entry; walk from newest
    to oldest and take the first that still exists on disk. Fixed 2026-07-18
    after the House Arcturus rename dropped both portraits twice."""
    if dest.exists():
        return dest
    for old_slug in reversed(RENAMES.get(dest_rel, [])):
        candidate = CONTENT_DIR / (old_slug + ".md")
        if candidate.exists():
            return candidate
    return None


def sync_page(src_name, dest_rel):
    src = ONTOS_SETTING / src_name
    text = src.read_text()
    src_fm, body = split_frontmatter(text)
    infobox_lines = extract_infobox_fields(src_fm)
    current_date = extract_current_date(src_fm)
    body = strip_callouts(body)
    body, image_caption = strip_leading_image(body)
    body = strip_meta_lines(body)
    body = drop_empty_headings(body)
    body = clean_blank_runs(body)

    dest = CONTENT_DIR / dest_rel
    marker_block = None
    submap_block = None
    image_block = None
    carry_src = carry_forward_source(dest, dest_rel)
    if carry_src is not None:
        existing_fm, _ = split_frontmatter(carry_src.read_text())
        marker_block = extract_marker_block(existing_fm)
        submap_block = extract_submap_block(existing_fm)
        image_block = extract_image_block(existing_fm)

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        render(
            TITLES[src_name], marker_block, body, image_block, infobox_lines, submap_block,
            alias_slugs=RENAMES.get(dest_rel), image_caption=image_caption,
            current_date=current_date,
        )
    )
    return dest


def main():
    written = []
    for src_name, dest_rel in PAGE_MAP.items():
        dest = sync_page(src_name, dest_rel)
        written.append(dest)

    print(f"Synced {len(written)} page(s) from Ontos:")
    for w in sorted(str(d.relative_to(CONTENT_DIR)) for d in written):
        print(f"  {w}")

    print(f"\nNot public (everything on the page is GM-only; kept out of PAGE_MAP):")
    for name in sorted(NOT_YET_PUBLIC):
        print(f"  {name}")

    print(f"\nContent-only (hand-maintained in content/, not synced; already live):")
    for name in sorted(CONTENT_ONLY):
        print(f"  {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
