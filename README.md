# Wiki template

A campaign-agnostic base for a public, spoiler-safe worldbuilding wiki with an interactive map, published with [Quartz v4](https://quartz.jzhao.xyz/). Create a new wiki with GitHub's **Use this template** button (not a fork), then wire it up as below.

## How this repo works

`content/` is a **generated build artifact**, not hand-edited. The GM's actual wiki lives in a private Obsidian vault (Ontos), annotated with two custom callout types:

- `[!gm-only]` — an in-world secret not yet revealed to players
- `[!gm-notes]` — permanent author-side content (real-world citations, planning notes) never shown to players

`scripts/sync-from-ontos.py` reads that source, strips both callout types, trims frontmatter to `title:` plus the typed-infobox fields, and writes the result here. Editing a file under `content/` directly is safe only for presentation-only data (map marker coordinates, a page's portrait embed, `changelog.md`), which the sync preserves; any lore text there is overwritten on the next run. Edit the source vault instead.

## The map

`content/map.md` and `content/pt/map.md` hold the interactive map: a `base` code block with one `leaflet-map` view whose `image:` is the background, `assets/jth-map.svg`. The two map pages and everything in `content/assets/` are maintained here. The sync never overwrites them; it only adds a page's portrait to `assets/` when one is missing. `quartz/plugins/transformers/leafletMapPlugin.ts` draws the map.

### Map image and rumor labels

The map script in the GM's vault (`jth-map-compositor.py`, run on the private key map) draws `assets/jth-map.svg`. With `--overlay` it also writes `assets/jth-map-rumors.json`. That file holds, for each region that has a rumor and at least one revealed hex, its revealed hex centers and its rumor in English and Portuguese. Region names and the rumors of unexplored regions never leave the vault. A map view shows the labels when it sets `overlay:` to that file and `lang:` to `en` or `pt`. Each rumor sits just outside the explored area on its region's side, the region's hexes light up on hover, and a Rumors switch in the map's layer menu hides the labels. When the key map changes, rerun the script and replace both files here.

### Markers

A page puts itself on the map with a `marker:` list in its frontmatter. `coordinates` is required, as `"lat, lng"` in map pixels: `lat` counts up from the image's bottom edge, `lng` across from its left edge. The optional fields are `mapName` (below), `icon` (a Lucide icon name), `colour`, `minZoom` and `category` (`settlement`, `holy-site`, `landmark` or `nation`; each category gets its own switch in the layer menu). A marker is a pin unless it sets `shape: hex`. A hex marker is a clickable hexagon centered on `coordinates`, with `size` as its radius in map pixels (48 matches one map hex), so it covers a hex exactly at every zoom level. The sync carries each page's `marker:` block forward, so markers are edited here.

Each language has its own map. The English map view sets `mapName: en` and the Portuguese one `mapName: pt`, and a marker with `mapName` shows only on the map of that name. A marker without it shows on every map, linking to whichever page carries it. So a place gets a marker on both its English and its Portuguese page, each naming its own map, and each map links to the page in its own language.

```yaml
marker:
    - mapName: en
      coordinates: "432, 496"
      icon: lucide-castle
      colour: "#c0883a"
      category: settlement
      shape: hex
      size: 48
```

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
