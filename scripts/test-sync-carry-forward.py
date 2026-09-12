#!/usr/bin/env python3
"""
Unit tests for sync-from-ontos.py's presentation-data carry-forward: the
`marker:` map-pin block, the `submap:` local-map block, and the `image:`
portrait filename must survive a re-sync verbatim (including YAML comment
lines inside a block), because all three exist only in content/ and would
otherwise be wiped every time the page is regenerated from the GM's source.

Pure-function tests on fixtures; never reads the Ontos vault and never
touches content/. Run from the repo root:
    python3 scripts/test-sync-carry-forward.py
"""
import importlib.util
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "sync_from_ontos", Path(__file__).resolve().parent / "sync-from-ontos.py"
)
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)

MARKER_BLOCK = """marker:
    - coordinates: "900, 1750"
      icon: lucide-building-2
      colour: "#c98a4b"
      category: settlement"""

SUBMAP_BLOCK = """submap:
    # Placeholder art: local pin coordinates are in this image's own pixel
    # space and will NOT survive the art swap.
    image: assets/map-placeholder.png
    caption: Annoying dog stole the map
    minZoom: 0
    maxZoom: 2
    defaultZoom: 1
    zoomDelta: 0.5
    markers:
        - name: You are here
          coordinates: "155, 180"
          icon: lucide-paw-print"""

IMAGE_LINE = "image: drinmery.jpg"

# What a destination file looks like after a previous sync: title + typed
# infobox fields from the source, image/marker/submap presentation data
# hand-maintained here.
EXISTING_DEST = f"""---
title: Drinmery
kind: location
nation: "[[jesthaen|Jesthaen]]"
{IMAGE_LINE}
{MARKER_BLOCK}
{SUBMAP_BLOCK}
---

Old body text about Drinmery.
"""


def test_extracts_marker_block():
    fm, _ = sync.split_frontmatter(EXISTING_DEST)
    assert sync.extract_marker_block(fm) == MARKER_BLOCK, "marker block not extracted verbatim"


def test_extracts_submap_block():
    fm, _ = sync.split_frontmatter(EXISTING_DEST)
    assert sync.extract_submap_block(fm) == SUBMAP_BLOCK, "submap block not extracted verbatim"


def test_extracts_image_block():
    fm, _ = sync.split_frontmatter(EXISTING_DEST)
    assert sync.extract_image_block(fm) == IMAGE_LINE, "image line not extracted verbatim"


def test_missing_blocks_return_none():
    fm, _ = sync.split_frontmatter("---\ntitle: Bare\nkind: location\n---\n\nBody.\n")
    assert sync.extract_marker_block(fm) is None
    assert sync.extract_submap_block(fm) is None
    assert sync.extract_image_block(fm) is None


def test_image_line_does_not_match_marker_or_submap_extractor():
    fm, _ = sync.split_frontmatter(f"---\ntitle: X\n{IMAGE_LINE}\n---\n\nBody.\n")
    assert sync.extract_marker_block(fm) is None
    assert sync.extract_submap_block(fm) is None
    assert sync.extract_image_block(fm) == IMAGE_LINE


def test_submap_key_does_not_match_marker_extractor():
    fm, _ = sync.split_frontmatter(f"---\ntitle: X\n{SUBMAP_BLOCK}\n---\n\nBody.\n")
    assert sync.extract_marker_block(fm) is None
    assert sync.extract_submap_block(fm) == SUBMAP_BLOCK


def test_resync_round_trip_preserves_all_presentation_data():
    """Simulate sync_page's carry-forward: extract from the existing dest,
    render a fresh page around a new body, and confirm a second extraction
    still yields the identical image/marker/submap data (so N re-syncs are
    lossless)."""
    fm, _ = sync.split_frontmatter(EXISTING_DEST)
    image = sync.extract_image_block(fm)
    marker = sync.extract_marker_block(fm)
    submap = sync.extract_submap_block(fm)
    rendered = sync.render(
        "Drinmery",
        marker,
        "New body text from a re-sync.",
        image_block=image,
        infobox_lines=["kind: location", 'nation: "[[jesthaen|Jesthaen]]"'],
        submap_block=submap,
    )
    fm2, body2 = sync.split_frontmatter(rendered)
    assert sync.extract_image_block(fm2) == IMAGE_LINE, "image line lost on re-sync"
    assert sync.extract_marker_block(fm2) == MARKER_BLOCK, "marker block lost on re-sync"
    assert sync.extract_submap_block(fm2) == SUBMAP_BLOCK, "submap block lost on re-sync"
    assert "New body text from a re-sync." in body2


def test_alias_slugs_render_as_frontmatter_list():
    """A page in the RENAMES table must carry its old path(s) as a Quartz
    `aliases:` list so the AliasRedirects emitter keeps its old URL
    redirecting after every re-sync."""
    rendered = sync.render(
        "Crater Lake", None, "Body.", alias_slugs=["locations/crater-lake"]
    )
    fm, _ = sync.split_frontmatter(rendered)
    lines = fm.splitlines()
    assert "aliases:" in lines, "aliases: key missing"
    assert "  - locations/crater-lake" in lines, "alias slug missing/misformatted"


def test_alias_lines_do_not_disturb_carry_forward():
    """aliases: sits in the same frontmatter as the carried marker/submap
    blocks; adding it must not break their verbatim round trip."""
    rendered = sync.render(
        "Drinmery",
        MARKER_BLOCK,
        "Body.",
        infobox_lines=["kind: location", 'nation: "[[jesthaen|Jesthaen]]"'],
        submap_block=SUBMAP_BLOCK,
        alias_slugs=["old/drinmery-path"],
    )
    fm, _ = sync.split_frontmatter(rendered)
    assert sync.extract_marker_block(fm) == MARKER_BLOCK, "marker block broken by aliases"
    assert sync.extract_submap_block(fm) == SUBMAP_BLOCK, "submap block broken by aliases"
    assert "  - old/drinmery-path" in fm.splitlines()


def test_renames_table_is_consistent_with_page_map():
    """Every RENAMES key must be a current PAGE_MAP destination (else the
    alias would never be written), and no alias may equal the page's own
    current slug (a self-redirect would shadow the real page)."""
    dests = set(sync.PAGE_MAP.values())
    for dest, old_slugs in sync.RENAMES.items():
        assert dest in dests, f"RENAMES key {dest} is not a PAGE_MAP destination"
        current_slug = dest[: -len(".md")] if dest.endswith(".md") else dest
        for old in old_slugs:
            assert old != current_slug, f"{dest} aliases its own current path"


def test_carry_forward_source_prefers_existing_destination(tmp_path):
    """When the destination already exists, that file is the carry-forward
    source (the normal re-sync case)."""
    content_dir = tmp_path
    dest_rel = "npcs/hesper-arcturus.md"
    dest = content_dir / dest_rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(EXISTING_DEST)
    assert sync.carry_forward_source(dest, dest_rel) == dest


def test_carry_forward_source_falls_back_to_most_recent_rename(tmp_path):
    """The bug fix: when the destination is brand new (a page rename), fall
    back to the most-recent prior destination in RENAMES, whose content/ file
    still holds the image:/marker:/submap: presentation data. Most-recent =
    last element of the RENAMES list (newly-old slugs are appended)."""
    content_dir = tmp_path
    dest_rel = "npcs/hesper-arcturus.md"
    dest = content_dir / dest_rel  # does NOT exist yet
    # Two prior destinations; only the most-recent one holds the real data.
    old_original = content_dir / "npcs/hesper.md"
    old_recent = content_dir / "npcs/hesper_arcturus.md"
    for p in (old_original, old_recent):
        p.parent.mkdir(parents=True, exist_ok=True)
    old_original.write_text("---\ntitle: Hesper\nimage: stale-original.jpg\n---\n\nBody.\n")
    old_recent.write_text(EXISTING_DEST)
    saved = (sync.RENAMES, sync.CONTENT_DIR)
    try:
        sync.CONTENT_DIR = content_dir
        sync.RENAMES = {"npcs/hesper-arcturus.md": ["npcs/hesper", "npcs/hesper_arcturus"]}
        src = sync.carry_forward_source(dest, dest_rel)
    finally:
        (sync.RENAMES, sync.CONTENT_DIR) = saved
    assert src == old_recent, "did not pick the most-recent prior destination"
    fm, _ = sync.split_frontmatter(src.read_text())
    assert sync.extract_image_block(fm) == IMAGE_LINE


def test_carry_forward_source_none_when_new_and_no_rename(tmp_path):
    """A genuinely new page with no RENAMES entry has nothing to carry from."""
    content_dir = tmp_path
    dest_rel = "npcs/brand-new.md"
    dest = content_dir / dest_rel
    saved = (sync.RENAMES, sync.CONTENT_DIR)
    try:
        sync.CONTENT_DIR = content_dir
        sync.RENAMES = {}
        assert sync.carry_forward_source(dest, dest_rel) is None
    finally:
        (sync.RENAMES, sync.CONTENT_DIR) = saved


def test_carry_forward_source_skips_missing_old_destinations(tmp_path):
    """If the most-recent prior destination file was already deleted, fall
    through to an older one that still exists rather than returning it blind."""
    content_dir = tmp_path
    dest_rel = "npcs/hesper-arcturus.md"
    dest = content_dir / dest_rel
    old_original = content_dir / "npcs/hesper.md"
    old_original.parent.mkdir(parents=True, exist_ok=True)
    old_original.write_text(EXISTING_DEST)  # only the oldest survives
    saved = (sync.RENAMES, sync.CONTENT_DIR)
    try:
        sync.CONTENT_DIR = content_dir
        sync.RENAMES = {"npcs/hesper-arcturus.md": ["npcs/hesper", "npcs/hesper_arcturus"]}
        src = sync.carry_forward_source(dest, dest_rel)
    finally:
        (sync.RENAMES, sync.CONTENT_DIR) = saved
    assert src == old_original


def test_sync_page_carries_image_across_a_rename(tmp_path):
    """End-to-end regression for the real 2026-07-18 bug: rename the source
    file, point PAGE_MAP/TITLES/RENAMES at the new slug, and confirm sync_page
    writes the new destination WITH the portrait recovered from the old one."""
    root = tmp_path
    ontos = root / "ontos-setting"
    content = root / "content"
    ontos.mkdir(parents=True, exist_ok=True)
    (content / "npcs").mkdir(parents=True, exist_ok=True)
    # The old published page already carries the portrait (content/-only data).
    (content / "npcs/izar_arcturus.md").write_text(
        "---\ntitle: Izar Arcturus\nimage: izar.png\nkind: person\n---\n\nOld body.\n"
    )
    # The renamed Ontos source (no image: in source, per rule 26).
    (ontos / "izar-arcturus.md").write_text(
        "---\ntitle: Izar Arcturus\nkind: person\n---\n\nNew body from the source.\n"
    )
    saved = (sync.ONTOS_SETTING, sync.CONTENT_DIR, sync.PAGE_MAP, sync.TITLES, sync.RENAMES)
    try:
        sync.ONTOS_SETTING = ontos
        sync.CONTENT_DIR = content
        sync.PAGE_MAP = {"izar-arcturus.md": "npcs/izar-arcturus.md"}
        sync.TITLES = {"izar-arcturus.md": "Izar Arcturus"}
        sync.RENAMES = {"npcs/izar-arcturus.md": ["npcs/izar", "npcs/izar_arcturus"]}
        dest = sync.sync_page("izar-arcturus.md", "npcs/izar-arcturus.md")
    finally:
        (sync.ONTOS_SETTING, sync.CONTENT_DIR, sync.PAGE_MAP, sync.TITLES, sync.RENAMES) = saved
    fm, body = sync.split_frontmatter(dest.read_text())
    assert sync.extract_image_block(fm) == "image: izar.png", "portrait dropped across rename"
    assert "New body from the source." in body, "new source body not synced"


def main():
    import inspect
    import shutil
    import tempfile

    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        # Tests that declare a `tmp_path` parameter get a fresh temp dir,
        # cleaned up after; the rest are pure-fixture tests that take nothing.
        # `tmp_path` is also pytest's built-in fixture of the same shape, so
        # these run identically under `pytest scripts/test-sync-carry-forward.py`.
        if "tmp_path" in inspect.signature(t).parameters:
            tmp = Path(tempfile.mkdtemp(prefix="sync-carry-test-"))
            try:
                t(tmp)
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
        else:
            t()
        print(f"  PASS {t.__name__}")
    print(f"{len(tests)} test(s) passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
