#!/usr/bin/env python3
"""
Unit tests for sync-from-ontos.py's wikilink rewrite: a bilingual wiki links its
sibling pages by the local `.en` / `.pt` source basename so the link resolves in
Obsidian, and the sync must rewrite that to the published slug on the way into
content/. A monolingual wiki (source basename == slug) must pass through
byte-for-byte, so the identity case is asserted too.

Pure-function tests on the module's own `build_link_table` / `rewrite_wikilinks`;
never reads the vault, never touches content/. Run from the repo root:
    python3 scripts/test-link-rewrite.py
"""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "sync_from_ontos", Path(__file__).resolve().parent / "sync-from-ontos.py"
)
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)

# The real per-wiki table for JtH: PAGE_MAP-derived (non-identity) pairs plus the
# LINK_REWRITE content-only stubs. Built once here so the tests exercise the
# actual live config, not a hand-copied duplicate.
TABLE = sync.build_link_table()

passed = 0
failed = 0


def check(name, got, want):
    global passed, failed
    if got == want:
        passed += 1
        print(f"  PASS {name}")
    else:
        failed += 1
        print(f"  FAIL {name}\n    got:  {got!r}\n    want: {want!r}")


def rw(body):
    return sync.rewrite_wikilinks(body, TABLE)


# --- table shape ------------------------------------------------------------
check("en_page_maps_to_bare_slug", TABLE.get("gazetteer.en"), "gazetteer")
check("pt_page_maps_to_pt_slug", TABLE.get("gazetteer.pt"), "pt/gazetteer")
check("nested_en_maps_to_folder_slug", TABLE.get("marrogate.en"), "gazetteer/marrogate")
check("nested_pt_maps_to_pt_folder_slug", TABLE.get("marrogate.pt"), "pt/gazetteer/marrogate")
check("content_only_stub_en", TABLE.get("map.en"), "map")
check("content_only_stub_pt", TABLE.get("map.pt"), "pt/map")

# --- body rewriting ---------------------------------------------------------
check("aliased_en_link", rw("see [[gazetteer.en|Gazetteer]]."), "see [[gazetteer|Gazetteer]].")
check("aliased_pt_link", rw("ver [[gazetteer.pt|Gazetteer]]."), "ver [[pt/gazetteer|Gazetteer]].")
check("map_stub_en", rw("[[map.en|The Map]]"), "[[map|The Map]]")
check("map_stub_pt", rw("[[map.pt|O Mapa]]"), "[[pt/map|O Mapa]]")
check("nested_en", rw("[[marrogate.en|Marrogate]]"), "[[gazetteer/marrogate|Marrogate]]")
check(
    "heading_anchor_preserved",
    rw("[[terranamancy.en#Echo-leveling|Echo-leveling]]"),
    "[[terranamancy#Echo-leveling|Echo-leveling]]",
)
check("bare_link_no_alias", rw("[[world.en]]"), "[[world]]")
check("image_embed_untouched", rw("![[hex-map.webp]]"), "![[hex-map.webp]]")
check("unknown_target_untouched", rw("[[colossus-of-the-drylands|Colossus]]"),
      "[[colossus-of-the-drylands|Colossus]]")
check("multiple_links_one_line",
      rw("[[world.en|world]] and [[house-rules.en|rules]]"),
      "[[world|world]] and [[house-rules|rules]]")

# --- monolingual identity guarantee (Althas byte-identity) ------------------
identity_table = {}  # a monolingual wiki contributes only identity pairs -> empty
body = "The [[voldaen|Voldaen]] link and the [[map]] stub stay verbatim."
check("monolingual_is_noop", sync.rewrite_wikilinks(body, identity_table), body)

print(f"\n{passed} test(s) passed, {failed} failed.")
raise SystemExit(1 if failed else 0)
