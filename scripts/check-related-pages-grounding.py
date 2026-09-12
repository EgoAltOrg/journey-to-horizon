#!/usr/bin/env python3
"""
Spoiler-exposure grounding gate (spec: Ontos ut-supra-sic-infra
specs/althas-spoiler-exposure-gate-design.md, 2026-07-17).

The 2026-07-16 leak class: a public "## Related pages" bullet (or an infobox
field value) names another page, but the ONLY thing connecting the two is a
relationship whose explanation is correctly wrapped [!gm-only]. Every secret
sentence is hidden, yet the link itself still tells the player the connection
exists. The manual audit that fixed the original leak asked one question per
claim: does the target's name appear anywhere in this page's own surviving
public prose? This script mechanizes exactly that question.

What it checks (per public page in content/):

  1. Related Pages grounding (FAIL): every wikilink in the "## Related pages"
     section must be grounded: the target's display title (or a wikilink to
     it) appears in the page's own prose OUTSIDE that section. An inline link
     inside a sentence self-grounds by construction (its sentence is public
     prose stating the connection); a bare list bullet asserts a relationship
     with no stated reason, so it needs grounding elsewhere on the page.
  2. Infobox field anomalies (WARN only): whitelisted frontmatter fields
     pass to the site verbatim with no gm-only awareness, but they are also
     intended-public by whitelist design and render visibly on the page card,
     so a field naming an entity the body never mentions is surfaced for the
     eye rather than blocking. A SECRET name in a field is a hard FAIL via
     check 3, which scans the whole file including frontmatter.
  3. Secret-entity mentions (FAIL): any NOT_YET_PUBLIC entity's display title
     appearing anywhere in a public file (prose, frontmatter, Mermaid labels)
     tells players the entity exists. Word-boundary, case-insensitive,
     hyphen/space tolerant.
  4. GM-callout remnants (FAIL): a [!gm-only]/[!gm-notes] marker surviving in
     content/ means the strip itself broke. Public callouts like [!note] are
     legitimate and NOT flagged (narrower than the spec's draft wording,
     which would false-positive on the 5 [!note] callouts live today).
  5. Bare-link bullets outside Related Pages (WARN only): a "- [[x]]" line
     under some other heading is usually contextually grounded by its
     heading; flagged for the human eye, never blocks the publish.

Reports only. There is deliberately NO --fix: whether an ungrounded claim
moves into [!gm-only] in the Ontos source or joins the allowlist is exactly
the judgment call a human owns (root CLAUDE.md rule 25). Exits non-zero on
any FAIL, mirroring check-infobox-fields.py, so it can gate the publish.

Allowlist (scripts/related-pages-allowlist.json): human-owned exceptions,
small enough to review during every publish; unused entries are reported so
it never silently accumulates. Structure:
  {
    "hub_targets":  ["diplomacy", ...],   // site-wide overview/utility pages
                                          // any page may link without grounding
    "public_names": { "Izar": "reason" }, // NOT_YET_PUBLIC entities whose NAME
                                          // is deliberately public knowledge
                                          // (only their page is withheld)
    "pages": { "<content-relative path>": { "<target slug>": "<reason>" } }
  }

Grounding also accepts, by construction (no allowlist entry needed):
  - the page's own visible infobox field values (they render publicly);
  - singular/plural title variants ("performed a miracle" grounds Miracles);
  - a folder index linking pages inside its own folder (containment IS the
    stated relationship, e.g. Jesthaen's page listing Drinmery).
"""
import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
DEFAULT_CONTENT = SCRIPTS_DIR.parent / "content"
DEFAULT_ALLOWLIST = SCRIPTS_DIR / "related-pages-allowlist.json"

# Same target regex family as check-broken-links.py (handles table-escaped \|).
LINK_RE = re.compile(r"\[\[([^\]|#\\]+)(\\?\|([^\]]+))?\]\]")
# Related-pages heading in every language a wiki publishes: the grounding
# (spoiler) check only fires on links UNDER this heading, so a language whose
# heading is missing here would silently escape the gate. Add each new
# language's heading as the wiki adds the language (EN + European Portuguese
# today).
RP_HEADING_RE = re.compile(
    r"^#{1,6}\s+(related pages|see also|p[áa]ginas relacionadas)\s*$", re.IGNORECASE
)
HEADING_RE = re.compile(r"^#{1,6}\s")
# A list line that is nothing but a wikilink, optionally with ": description".
BARE_BULLET_RE = re.compile(r"^(\s*-\s*)\[\[([^\]|#\\]+)(\\?\|([^\]]+))?\]\](\s*:\s*(.*))?\s*$")
GM_REMNANT_RE = re.compile(r"^\s*>\s*\[!(gm-only|gm-notes)\]", re.IGNORECASE)
FRONTMATTER_RE = re.compile(r"^---\n(.*?\n)---\n?", re.DOTALL)
# Frontmatter keys that are presentation/plumbing, never relational claims.
FM_SKIP_KEYS = {"title", "aliases", "image", "image_caption", "marker", "submap"}

# Cardinal-number words. A title like "The Seven" whose only word after the
# article is a number must not be matched by that bare number in prose (see
# title_pattern): "seven" appears in ordinary sentences ("five to seven feet").
NUMBER_WORDS = {
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
    "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
    "sixteen", "seventeen", "eighteen", "nineteen", "twenty", "thirty",
    "forty", "fifty", "sixty", "seventy", "eighty", "ninety", "hundred",
    "thousand", "million",
}

# Extra surface forms to also flag for a specific secret title (keyed by the
# lowercased title). Opt-in per entity, NOT a blanket morphological rule: use it
# only where the word is archaic enough never to appear in public prose by
# accident, so matching its singular costs no false positives. 'The Threnodies'
# qualifies (a threnody is an obscure funeral lament). A common-word secret like
# 'Heresies' is deliberately NOT here: the singular 'heresy' is ordinary Church
# vocabulary ('named the claim heresy', 'between faith and heresy') and the
# public civil war 'Valerion's Heresy' is named across the live wiki, so a y-ies
# rule there flagged 36 public lines (2026-09-04). The singular/plural split is
# the firewall that keeps the secret 'Heresies' distinct from the public 'Heresy'.
EXTRA_TITLE_FORMS = {
    "the threnodies": ["threnody"],
}


def load_sync_module():
    """Import sync-from-ontos.py (hyphenated name) for NOT_YET_PUBLIC/TITLES:
    the secret list lives there and must never be duplicated."""
    path = SCRIPTS_DIR / "sync-from-ontos.py"
    spec = importlib.util.spec_from_file_location("sync_from_ontos", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def split_frontmatter(text):
    m = FRONTMATTER_RE.match(text)
    if not m:
        return "", text
    return m.group(1), text[m.end():]


def frontmatter_scalar_fields(fm_text):
    """Top-level `key: value` lines, minus presentation keys and their
    indented continuation blocks. Values returned verbatim."""
    fields = {}
    skip_block = False
    for line in fm_text.splitlines():
        if line[:1] in (" ", "\t") or line.strip() == "":
            continue  # continuation of a previous block; scalars don't have them
        skip_block = False
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", line)
        if not m:
            continue
        key, value = m.group(1), m.group(2).strip().strip("\"'")
        if key in FM_SKIP_KEYS or not value:
            continue
        fields[key] = value
    return fields


def page_title(fm_text, fallback):
    m = re.search(r"^title:\s*(.+)$", fm_text, re.MULTILINE)
    return m.group(1).strip().strip("\"'") if m else fallback


def title_pattern(title):
    """Word-boundary, case-insensitive, hyphen/space-tolerant matcher for a
    display title. 'The Hilltop Night Zone' also matches without 'The ', and
    the last word matches with or without a trailing s ('performed a miracle'
    grounds a link to Miracles; 'a giant' grounds Giants).

    There is no blanket y<->ies rule: matching an -ies plural to its -y singular
    conflates entities the singular/plural split keeps apart (the secret
    'Heresies' vs the public civil war 'Valerion's Heresy'). EXTRA_TITLE_FORMS
    instead opts a specific title into extra surface forms where its word is
    archaic enough to be a safe leak signal ('The Threnodies' also catches the
    singular 'threnody'); see that constant for the reasoning."""
    parts = re.split(r"[\s-]+", title.strip())
    variants = [parts]
    # Also match the title without its leading article ('The Hilltop Night Zone'
    # -> 'Hilltop Night Zone', 'The Stargazers' -> bare 'stargazer' so a leaked
    # "Castorius is a stargazer" is caught). The one exception: a single-word
    # remainder that is a NUMBER ('The Seven' -> 'seven') would match the number
    # in ordinary prose ('five to seven feet', 'seven days'), a false positive
    # that blocks every publish, so 'The Seven' requires its article. This is
    # the only remainder class common enough in prose to warrant the exception;
    # distinctive proper nouns keep their bare-word leak matching.
    if parts and parts[0].lower() == "the" and len(parts) > 1:
        remainder = parts[1:]
        bare_is_number = len(remainder) == 1 and (
            remainder[0].isdigit() or remainder[0].lower() in NUMBER_WORDS
        )
        if not bare_is_number:
            variants.append(remainder)
    alts = []
    for v in variants:
        escaped = [re.escape(p) for p in v]
        last = v[-1]
        if last.lower().endswith("s") and len(last) > 3:
            escaped[-1] = re.escape(last[:-1]) + "s?"
        else:
            escaped[-1] = re.escape(last) + "s?"
        alts.append(r"[\s-]+".join(escaped))
    for form in EXTRA_TITLE_FORMS.get(title.strip().lower(), ()):
        alts.append(re.escape(form))
    return re.compile(r"(?<![\w-])(" + "|".join(alts) + r")(?![\w-])", re.IGNORECASE)


def render_links(text):
    """Replace wikilinks with their visible display text so title matching
    sees what a player sees."""
    return LINK_RE.sub(lambda m: (m.group(3) or m.group(1)).strip(), text)


def _shortest_key(slug):
    """The last path segment a Quartz "shortest" match compares against, with
    a folder's own index.md standing in for its parent folder name."""
    parts = slug.split("/")
    if parts[-1] == "index" and len(parts) >= 2:
        return parts[-2]
    return parts[-1]


def resolve_slug(target, slugs, slug_set):
    """Resolve an Obsidian wikilink target to a content slug the way Quartz's
    markdownLinkResolution:"shortest" does (quartz/util/path.ts, transformLink):
    a UNIQUE last-segment match wins; otherwise the target is an absolute root-
    relative slug (resolving only if that slug, or that folder's index, exists);
    a trailing slash is a folder link, resolving only to that folder's index.
    This is what makes a bilingual wiki's [[pt/world]] resolve to pt/world's own
    page (title "O Mundo") instead of colliding with the EN "world" by basename.
    Returns the resolved slug (lowercased) or None.

    Case-INSENSITIVE (lowercases target and slugs): this gate keys titles and
    slugs lowercase throughout and errs toward grounding, so a casing mismatch
    never blocks a publish. Its twin resolve_target in check-broken-links.py is
    case-sensitive to stay faithful to Quartz (which never lowercases); a link
    that only Quartz breaks is the broken-links gate's job to flag, not this
    one's. Both gate the same slug list, so on all-lowercase filenames (the
    convention) they agree."""
    raw = target.split("#", 1)[0].strip()
    is_folder = raw.endswith("/")
    canonical = raw.strip("/").lower()
    if not canonical:
        return None
    if is_folder:
        return f"{canonical}/index" if f"{canonical}/index" in slug_set else None
    matches = [s for s in slugs if _shortest_key(s) == canonical]
    if len(matches) == 1:
        return matches[0]
    if canonical in slug_set:
        return canonical
    if f"{canonical}/index" in slug_set:
        return f"{canonical}/index"
    return None


def resolve_title(target, titles_by_slug, slugs, slug_set):
    """Display title of whatever page `target` resolves to, or None. Tries a
    direct full-slug hit first (covers [[pt/world]] and root [[world]] alike,
    since a root page's slug is its own basename), then falls back to Quartz's
    shortest resolver for a bare link to a nested page."""
    key = target.strip().strip("/").lower()
    if key in titles_by_slug:
        return titles_by_slug[key]
    resolved = resolve_slug(target, slugs, slug_set)
    return titles_by_slug.get(resolved) if resolved else None


class Page:
    def __init__(self, path, content_dir):
        self.path = path
        self.rel = str(path.relative_to(content_dir))
        text = path.read_text()
        self.raw = text
        fm, body = split_frontmatter(text)
        self.fm = fm
        self.body = body
        self.title = page_title(fm, path.stem)
        self.fields = frontmatter_scalar_fields(fm)
        # This page's full root-relative slug (POSIX, no .md, lowercase): its
        # identity for resolution. Keying on the full slug rather than the bare
        # basename is what keeps world.md and pt/world.md distinct.
        self.slug = path.relative_to(content_dir).with_suffix("").as_posix().lower()
        # Slugs that count as "this page itself" (self-links are not claims).
        self.self_slugs = {self.slug}

        # Partition body lines: RP-section lines / bare bullets / prose.
        lines = body.splitlines()
        self.rp_claims = []      # (lineno, target, display)
        self.body_bullets = []   # (lineno, target, display)  outside RP
        prose = []
        in_rp = False
        for lineno, line in enumerate(lines, 1):
            if HEADING_RE.match(line):
                in_rp = bool(RP_HEADING_RE.match(line))
                prose.append(line)
                continue
            bullet = BARE_BULLET_RE.match(line)
            if bullet:
                target = bullet.group(2).strip()
                display = (bullet.group(4) or target).strip()
                desc = bullet.group(6) or ""
                if in_rp:
                    self.rp_claims.append((lineno, target, display))
                else:
                    self.body_bullets.append((lineno, target, display))
                if desc:
                    prose.append(desc)  # a bullet's description is public prose
                continue
            if in_rp:
                continue  # non-bullet RP lines don't ground anything
            prose.append(line)
        self.corpus_raw = "\n".join(prose)
        # Infobox fields render publicly on the page card, so their values are
        # visible statements that ground an RP link (but a field value never
        # grounds its own claim: field checks use prose only, see below).
        fields_text = "\n".join(self.fields.values())
        self.corpus_rendered = render_links(self.corpus_raw + "\n" + fields_text)
        self.prose_rendered = render_links(self.corpus_raw)
        self.folder = str(Path(self.rel).parent).replace("\\", "/")

    def _names(self, target, titles_by_slug, slugs, slug_set, prose_only=False):
        """Does THIS page's own public content (prose + visible infobox values,
        outside the claim surfaces) name the given target, by wikilink or title?
        prose_only=True excludes infobox values."""
        if re.search(r"\[\[" + re.escape(target) + r"(\]\]|\\?\||#)", self.corpus_raw, re.IGNORECASE):
            return True
        title = resolve_title(target, titles_by_slug, slugs, slug_set)
        corpus = self.prose_rendered if prose_only else self.corpus_rendered
        return bool(title and title_pattern(title).search(corpus))

    def grounds(self, target, titles_by_slug, slugs, slug_set, slug_folders=None, by_slug=None, prose_only=False):
        """Is a link from this page to `target` grounded by public content, so
        it is NOT connected only by a still-hidden secret (rule 25)? Grounding
        is bidirectional: the connection counts as public if it's stated on
        EITHER page's public side, since a secret-only link is one neither
        public page justifies. Reciprocal Related Pages bullets don't count
        (the RP section is excluded from both corpora), so two ungrounded
        bullets can't circularly ground each other."""
        resolved = resolve_slug(target, slugs, slug_set) or target.strip().strip("/").lower()
        if resolved in self.self_slugs or resolved == "index":  # self_slugs == {self.slug}
            return True
        # Folder containment: a folder's index page linking a page inside its
        # own folder states the relationship by structure (Jesthaen -> Drinmery).
        if slug_folders is not None and self.path.stem == "index":
            target_folder = slug_folders.get(resolved, "")
            if target_folder == self.folder or target_folder.startswith(self.folder + "/"):
                return True
        # Forward: this page's public content names the target.
        if self._names(target, titles_by_slug, slugs, slug_set, prose_only):
            return True
        # Backward: the target page's public content names THIS page (by its own
        # slug, or its title). A connection publicly stated on the target's side
        # is public, so the link here is not a leak.
        if by_slug is not None:
            target_page = by_slug.get(resolved)
            if target_page is not None and target_page is not self:
                for s in self.self_slugs:
                    if target_page._names(s, titles_by_slug, slugs, slug_set):
                        return True
                if title_pattern(self.title).search(target_page.corpus_rendered):
                    return True
        return False


def build_title_map(content_dir):
    """slug (full root-relative, lowercase, no .md) -> display title, and slug ->
    containing folder, from content/ itself. Keying by the FULL slug rather than
    the bare basename is what keeps a bilingual wiki's world -> "The World" and
    pt/world -> "O Mundo" apart instead of one silently overwriting the other
    (the collision that made this gate check EN prose against a PT title). Also
    returns the slug list + set the shortest resolver needs."""
    titles = {}
    folders = {}
    for p in content_dir.rglob("*.md"):
        fm, _ = split_frontmatter(p.read_text())
        title = page_title(fm, p.stem)
        slug = p.relative_to(content_dir).with_suffix("").as_posix().lower()
        folders[slug] = str(p.parent.relative_to(content_dir)).replace("\\", "/")
        titles[slug] = title
    slug_set = set(titles)
    return titles, folders, sorted(slug_set), slug_set


def secret_matchers(sync_mod, public_names):
    """(entity name, compiled pattern) per NOT_YET_PUBLIC entry. Display title
    from TITLES when present; otherwise derived from the filename's parts.
    Entities in the allowlist's public_names are skipped: their page is
    withheld but their name is deliberately public knowledge (e.g. a person
    another public page openly narrates)."""
    matchers = []
    public_lower = {n.lower() for n in public_names}
    for name in sorted(sync_mod.NOT_YET_PUBLIC):
        title = sync_mod.TITLES.get(name, name[:-3].replace("-", " "))
        if title.lower() in public_lower:
            continue
        matchers.append((title, title_pattern(title)))
    return matchers


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--content-dir", type=Path, default=DEFAULT_CONTENT,
                    help="content/ folder to scan (default: repo's)")
    ap.add_argument("--allowlist", type=Path, default=DEFAULT_ALLOWLIST,
                    help="allowlist JSON (default: scripts/related-pages-allowlist.json)")
    args = ap.parse_args()
    content_dir = args.content_dir.resolve()

    allowlist = {}
    if args.allowlist.exists():
        allowlist = json.loads(args.allowlist.read_text())
    pages_allow = allowlist.get("pages", {})
    hub_targets = {t.lower() for t in allowlist.get("hub_targets", [])}
    public_names = allowlist.get("public_names", {})
    used_allowlist = set()

    sync_mod = load_sync_module()
    titles_by_slug, slug_folders, slugs, slug_set = build_title_map(content_dir)
    secrets = secret_matchers(sync_mod, public_names)

    failures = []
    warnings = []

    # Build every page first so grounding can look across pages (bidirectional).
    pages = [Page(p, content_dir) for p in sorted(content_dir.rglob("*.md"))]
    by_slug = {}
    for pg in pages:
        for s in pg.self_slugs:
            by_slug.setdefault(s, pg)

    for page in pages:
        page_allow = pages_allow.get(page.rel, {})

        # 4. GM-callout remnants: the strip itself must never leak a marker.
        for lineno, line in enumerate(page.raw.splitlines(), 1):
            if GM_REMNANT_RE.match(line):
                failures.append(f"{page.rel}:{lineno} GM callout marker survived the sync: {line.strip()[:80]}")

        # 3. Secret-entity mentions anywhere in the file (frontmatter included).
        rendered_full = render_links(page.raw)
        for title, pattern in secrets:
            for lineno, line in enumerate(rendered_full.splitlines(), 1):
                if pattern.search(line):
                    failures.append(f"{page.rel}:{lineno} names still-secret entity {title!r}: {line.strip()[:80]}")

        # The homepage is a table of contents: a link there says "this page is
        # public", not "these two pages are related". Grounding doesn't apply.
        if page.rel == "index.md":
            continue

        # 1. Related Pages grounding.
        for lineno, target, display in page.rp_claims:
            if target.lower() in hub_targets:
                used_allowlist.add(("hub", target.lower()))
                continue
            if target.lower() in page_allow:
                used_allowlist.add((page.rel, target.lower()))
                continue
            if not page.grounds(target, titles_by_slug, slugs, slug_set, slug_folders, by_slug):
                failures.append(
                    f"{page.rel}:{lineno} Related Pages link [[{target}|{display}]] has no grounding "
                    f"in this page's own public prose (rule 25: either the connecting fact is still "
                    f"gm-only, so the bullet moves into the same callout in the Ontos source, or "
                    f"allowlist it with a reason)"
                )

        # 2. Infobox/frontmatter field anomalies (WARN): fields are
        # intended-public by whitelist design, so a field naming an entity the
        # body never mentions is suspicious but not automatically a leak; a
        # SECRET name in a field is caught by check 3 above, which scans the
        # whole file. prose_only: a field value never grounds its own claim.
        for key, value in page.fields.items():
            claim_slugs = {m.group(1).strip().lower() for m in LINK_RE.finditer(value)}
            rendered_value = render_links(value)
            for slug, title in titles_by_slug.items():
                if slug in page.self_slugs or slug in claim_slugs:
                    continue
                if title_pattern(title).search(rendered_value):
                    claim_slugs.add(slug)
            for slug in sorted(claim_slugs):
                if slug in page.self_slugs or slug in hub_targets:
                    continue
                if slug in page_allow:
                    used_allowlist.add((page.rel, slug))
                    continue
                if not page.grounds(slug, titles_by_slug, slugs, slug_set, slug_folders, by_slug, prose_only=True):
                    warnings.append(
                        f"{page.rel} infobox field {key}: {value!r} names [[{slug}]], "
                        f"which the page body never mentions"
                    )

        # 5. Bare-link bullets outside RP: contextually grounded by their
        # heading more often than not; surfaced for the eye, never blocking.
        for lineno, target, display in page.body_bullets:
            if target.lower() in page_allow:
                used_allowlist.add((page.rel, target.lower()))
                continue
            if target.lower() in hub_targets:
                used_allowlist.add(("hub", target.lower()))
                continue
            if not page.grounds(target, titles_by_slug, slugs, slug_set, slug_folders, by_slug):
                warnings.append(f"{page.rel}:{lineno} bare list link [[{target}|{display}]] outside Related Pages, not restated in prose")

    stale = [
        f"{rel}: {slug} ({reason})"
        for rel, entries in pages_allow.items()
        for slug, reason in entries.items()
        if (rel, slug) not in used_allowlist
    ]
    stale += [
        f"hub_targets: {t}"
        for t in sorted(hub_targets)
        if ("hub", t) not in used_allowlist
    ]

    if warnings:
        print(f"{len(warnings)} warning(s) (non-blocking):")
        for w in warnings:
            print(f"  ~ {w}")
        print()
    if stale:
        print(f"{len(stale)} unused allowlist entr(ies) — prune so the list stays reviewable:")
        for s in stale:
            print(f"  ? {s}")
        print()
    if failures:
        print(f"{len(failures)} grounding/exposure failure(s):")
        for f in failures:
            print(f"  ✗ {f}")
        return 1
    print("All Related Pages links, infobox fields, and secret-entity checks pass.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
