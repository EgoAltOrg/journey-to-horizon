# Wiki template

A campaign-agnostic base for a public, spoiler-safe worldbuilding wiki with an interactive map, published with [Quartz v4](https://quartz.jzhao.xyz/). Create a new wiki with GitHub's **Use this template** button (not a fork), then wire it up as below.

## How this repo works

`content/` is a **generated build artifact**, not hand-edited. The GM's actual wiki lives in a private Obsidian vault (Ontos), annotated with two custom callout types:

- `[!gm-only]` — an in-world secret not yet revealed to players
- `[!gm-notes]` — permanent author-side content (real-world citations, planning notes) never shown to players

`scripts/sync-from-ontos.py` reads that source, strips both callout types, trims frontmatter to `title:` plus the typed-infobox fields, and writes the result here. Editing a file under `content/` directly is safe only for presentation-only data (map marker coordinates, a page's portrait embed, `changelog.md`), which the sync preserves; any lore text there is overwritten on the next run. Edit the source vault instead.

## Setting up a new wiki from this template

1. `scripts/sync_config.py` — the one file each wiki edits. Set `ONTOS_SETTING` (your source folder), `PAGE_MAP`, `TITLES`, and (as they arise) `RENAMES`, `NOT_YET_PUBLIC`, `CONTENT_ONLY`, `INFOBOX_KIND_FIELDS`.
2. `quartz.config.ts` — set `pageTitle`, `baseUrl` (`egoaltorg.github.io/<your-repo>`), and the theme colors.
3. `quartz.layout.ts` — adjust the top nav, the Explorer folder labels, and (optionally) whether the force graph shows.
4. Set the repo's commit identity if it needs a firewall (`git config user.name` / `user.email`).

## Publishing

1. `python3 scripts/sync-from-ontos.py`
2. `python3 scripts/check-broken-links.py --fix`
3. The gates: `check-spoiler-leak.py`, `check-embedded-assets.py`, `check-infobox-fields.py`, `check-title-casing.py`, `check-related-pages-grounding.py` (each reports; the spoiler and asset gates must exit 0)
4. `npx quartz build` (verify locally before pushing)
5. `git push` — deploys automatically via `.github/workflows/deploy.yml`

## Local dev

```
npm i
npx quartz build --serve
```

Built on [Quartz v4](https://github.com/jackyzha0/quartz) ([MIT licensed](LICENSE.txt)).
