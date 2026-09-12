#!/usr/bin/env python3
"""Unit tests for check-related-pages-grounding.py's title_pattern matcher.
Run: python3 scripts/test-check-related-pages-grounding.py"""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "check_related_pages_grounding",
    Path(__file__).resolve().parent / "check-related-pages-grounding.py",
)
grd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(grd)


def test_number_remainder_requires_article():
    # 'The Seven' must NOT reduce to the bare number 'seven': the 2026-09-04
    # false positives that this fix targets.
    p = grd.title_pattern("The Seven")
    assert not p.search("firbolg stand five to seven feet tall"), \
        "'The Seven' must not match the number 'seven' in prose"
    assert not p.search("the ritual lasts seven days"), \
        "'The Seven' must not match 'seven days'"


def test_number_remainder_still_matches_with_article():
    # The canonical name still grounds a real mention (leak detection intact).
    p = grd.title_pattern("The Seven")
    assert p.search("the Seven convened in secret"), \
        "'The Seven' must still match 'the Seven'"
    assert p.search("The Seven ruled from the shadows"), \
        "'The Seven' must still match 'The Seven'"


def test_distinctive_single_word_secret_keeps_bare_word_match():
    # The rule-29 regression guard: a distinctive single-word 'The X' secret
    # ('The Stargazers', where Castorius is secretly a Stargazer) MUST still be
    # caught by its bare word in prose. Only NUMBER remainders lose this; a
    # proper noun stays a leak signal, since a false positive here safely blocks
    # a publish while a false negative leaks a secret (rule 29).
    for title, leak in [
        ("The Stargazers", "Castorius is a stargazer"),
        ("The Observers", "one of the tower's observers slipped away"),
        ("The Threnodies", "chanting the old threnodies aloud"),
        ("The Threnodites", "the last threnodite fell"),
    ]:
        assert grd.title_pattern(title).search(leak), \
            f"{title!r} must still flag a bare-word leak: {leak!r}"


def test_threnodies_opts_into_its_singular():
    # 'The Threnodies' is opted into its singular via EXTRA_TITLE_FORMS: a
    # threnody is an obscure funeral lament, so matching 'threnody' costs no
    # false positives (it appears nowhere in public prose) while catching a
    # singular-form leak. The secret_matchers path derives the title as the
    # lowercase 'the threnodies', so probe that form too.
    for title in ("The Threnodies", "the threnodies"):
        assert grd.title_pattern(title).search("a single threnody survived"), \
            f"{title!r} must catch the opted-in singular 'threnody'"


def test_multi_word_number_title_still_drops_article():
    # The number exception is single-word-remainder ONLY: a multi-word remainder
    # that happens to contain a number still drops its article normally.
    p = grd.title_pattern("The Seven Sisters")
    assert p.search("they fled to Seven Sisters"), \
        "'The Seven Sisters' must still match without its article"


def test_multi_word_title_still_matches_without_article():
    # A 2+-word remainder is distinctive enough to stand alone: dropping 'The'
    # must still work so prose that omits the article grounds the link.
    p = grd.title_pattern("The Hilltop Night Zone")
    assert p.search("deep in the Hilltop Night Zone"), \
        "multi-word title must match with its article"
    assert p.search("a Hilltop Night Zone patrol"), \
        "multi-word title must still match without its article"


def test_two_word_remainder_edge_case():
    # 'The X Y' (three words, two-word remainder) must still drop the article.
    p = grd.title_pattern("The Council Five")
    assert p.search("The Council Five convened"), "must match full title"
    assert p.search("the Council Five's decree"), "must match with article, apostrophe-s"
    assert p.search("only Council Five knew"), \
        "two-word remainder must still match without the article"


def test_trailing_s_tolerance_preserved():
    # The last-word s? rule still holds for a plain (article-free) title.
    p = grd.title_pattern("Miracles")
    assert p.search("performed a miracle"), "'Miracles' should match 'miracle'"
    assert p.search("the Miracles of the faith"), "'Miracles' should match 'Miracles'"


def test_plural_title_does_not_match_singular_across_the_firewall():
    # The singular/plural split separates the secret 'Heresies' from the public
    # civil war 'Valerion's Heresy'. Matching the -ies plural to its -y singular
    # would flag every public mention of the Heresy as a leak (36 lines on
    # 2026-09-04), so the matcher stays deliberately NOT y<->ies aware.
    p = grd.title_pattern("Heresies")
    assert not p.search("the aftermath of Valerion's Heresy"), \
        "'Heresies' must NOT match the public singular 'Heresy'"
    assert p.search("the northern heresies spread"), \
        "'Heresies' must still match its own plural 'heresies'"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"  PASS {name}")
    print("All check-related-pages-grounding tests passed.")
