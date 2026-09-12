import { PageLayout, SharedLayout } from "./quartz/cfg"
import * as Component from "./quartz/components"

// Pages excluded from the force graph: hub/utility and tooling pages that either
// dominate the layout (the home page "/" and the changelog link to nearly
// everything) or are interactive tools rather than lore (the dice roller, the
// map). Each slug is dropped as a graph NODE (removeSlugs, so every link to it
// disappears too) AND the graph box is hidden on that page. Add your wiki's own
// hub/tool slugs here.
const graphExcludedSlugs = [
  "/",
  "changelog",
  "dice-roller",
  "map",
]

// Shared Graph config: the same local/global force-graph settings are used on
// every page that shows a graph (single notes AND content-bearing folder-root
// pages like the nations), so the excluded-slug list and the global force
// tuning live in one place.
const graphConfig = {
  localGraph: {
    removeSlugs: graphExcludedSlugs,
  },
  globalGraph: {
    repelForce: 0.5,
    // The default radial force pulls every node out to a ring at ~0.4x the
    // viewport, which is what actually spread the graph (independent of the
    // charge, so lowering repelForce did nothing). Disable it and cap the
    // charge's range so nodes only push their neighbours.
    enableRadial: false,
    distanceMax: 220,
    removeSlugs: graphExcludedSlugs,
  },
}

// components shared across all pages
export const sharedPageComponents: SharedLayout = {
  head: Component.Head(),
  header: [],
  // DiceRoller renders only on the dice-roller utility page (slug check), so
  // the bundled dice library and its UI never appear on any lore page. Its
  // client script re-binds on the "nav" SPA event and cleans up after itself.
  afterBody: [
    Component.ConditionalRender({
      component: Component.DiceRoller(),
      condition: (page) => page.fileData.slug === "dice-roller",
    }),
  ],
  footer: Component.Footer({
    links: {
      GitHub: "https://github.com/jackyzha0/quartz",
      "Discord Community": "https://discord.gg/cRFFHYye7t",
    },
  }),
}

// components for pages that display a single page (e.g. a single note)
export const defaultContentPageLayout: PageLayout = {
  beforeBody: [
    Component.ConditionalRender({
      component: Component.Breadcrumbs(),
      condition: (page) => page.fileData.slug !== "index",
    }),
    Component.ArticleTitle(),
    Component.ContentMeta(),
    Component.TagList(),
    // On mobile the right sidebar renders below the article, so the infobox
    // gets a mobile-only twin up here, right below the title block (same
    // MobileOnly/DesktopOnly pairing pattern as Spacer/TableOfContents).
    // Server-rendered only: no .toString()/new Function client script, so the
    // Explorer sortFn __name pitfall doesn't apply here.
    Component.MobileOnly(Component.Infobox()),
  ],
  left: [
    Component.PageTitle(),
    Component.MobileOnly(Component.Spacer()),
    Component.Flex({
      components: [
        {
          Component: Component.Search(),
          grow: true,
        },
        { Component: Component.Darkmode() },
        { Component: Component.ReaderMode() },
      ],
    }),
    Component.Explorer({
      // Title-case the top-level folder labels so the Explorer reads
      // "Organizations", "NPCs", "Player Characters" instead of raw lowercase
      // slugs. Nation folders (Voldaen, etc.) already get their title from
      // their index.md and aren't in the map, so `?? node.displayName` leaves
      // them untouched. SAME __name trap as sortFn below: this fn is
      // .toString()'d into the browser, so NO named inner const/function. An
      // inline object literal is safe (keep-names only wraps named fn/class
      // expressions), so the lookup table is written inline deliberately.
      mapFn: (node) => {
        if (node.isFolder) {
          node.displayName =
            {
              organizations: "Organizations",
              magic: "Magic",
              beings: "Beings",
              ancestries: "Ancestries",
              locations: "Locations",
              npcs: "NPCs",
              "player-characters": "Player Characters",
              setting: "Setting",
              events: "Events",
            }[node.displayName] ?? node.displayName
        }
      },
      // Sort ignoring a leading "The " so "The Holy See" files under H, etc.
      // NOTE: this fn is .toString()'d and run through `new Function` in the
      // browser, so it must be fully self-contained AND must not create any
      // named inner function/const: esbuild's keep-names wraps those in a
      // `__name(...)` helper that does not exist client-side (undefined ->
      // the Explorer silently dies). Keep the "strip the leading The" logic
      // inlined for exactly that reason. Verify in a browser after editing.
      sortFn: (a, b) => {
        if ((!a.isFolder && !b.isFolder) || (a.isFolder && b.isFolder)) {
          return a.displayName
            .replace(/^the\s+/i, "")
            .localeCompare(b.displayName.replace(/^the\s+/i, ""), undefined, {
              numeric: true,
              sensitivity: "base",
            })
        }
        if (!a.isFolder && b.isFolder) {
          return 1
        } else {
          return -1
        }
      },
    }),
  ],
  right: [
    Component.DesktopOnly(Component.Infobox()),
    // The graph box is hidden on pages that aren't in the graph themselves
    // (graphExcludedSlugs): a page dropped as a node has no graph to show. The
    // home page's FullSlug is "index" while its graph node is "/" (the
    // simplified slug removeSlugs matches), so normalize it before the check.
    Component.ConditionalRender({
      component: Component.Graph(graphConfig),
      condition: (page) => {
        const slug = page.fileData.slug ?? ""
        const normalized = slug === "index" ? "/" : slug
        return !graphExcludedSlugs.includes(normalized)
      },
    }),
    Component.DesktopOnly(Component.TableOfContents()),
    Component.Backlinks(),
  ],
}

// components for pages that display lists of pages  (e.g. tags or folders)
export const defaultListPageLayout: PageLayout = {
  // Nation pages are folder-index pages rendered with THIS list layout, not the
  // content layout, so the Infobox has to be mounted here too or a typed nation
  // index (kind: nation) never shows its infobox. The Infobox self-guards
  // (returns null unless the page has an `image:` or a valid `kind`), so a plain
  // tag/folder list page renders nothing. Same MobileOnly/DesktopOnly pairing as
  // defaultContentPageLayout.
  beforeBody: [
    Component.Breadcrumbs(),
    Component.ArticleTitle(),
    Component.ContentMeta(),
    Component.MobileOnly(Component.Infobox()),
  ],
  left: [
    Component.PageTitle(),
    Component.MobileOnly(Component.Spacer()),
    Component.Flex({
      components: [
        {
          Component: Component.Search(),
          grow: true,
        },
        { Component: Component.Darkmode() },
      ],
    }),
    Component.Explorer({
      // Title-case the top-level folder labels so the Explorer reads
      // "Organizations", "NPCs", "Player Characters" instead of raw lowercase
      // slugs. Nation folders (Voldaen, etc.) already get their title from
      // their index.md and aren't in the map, so `?? node.displayName` leaves
      // them untouched. SAME __name trap as sortFn below: this fn is
      // .toString()'d into the browser, so NO named inner const/function. An
      // inline object literal is safe (keep-names only wraps named fn/class
      // expressions), so the lookup table is written inline deliberately.
      mapFn: (node) => {
        if (node.isFolder) {
          node.displayName =
            {
              organizations: "Organizations",
              magic: "Magic",
              beings: "Beings",
              ancestries: "Ancestries",
              locations: "Locations",
              npcs: "NPCs",
              "player-characters": "Player Characters",
              setting: "Setting",
              events: "Events",
            }[node.displayName] ?? node.displayName
        }
      },
      // Sort ignoring a leading "The " so "The Holy See" files under H, etc.
      // NOTE: this fn is .toString()'d and run through `new Function` in the
      // browser, so it must be fully self-contained AND must not create any
      // named inner function/const: esbuild's keep-names wraps those in a
      // `__name(...)` helper that does not exist client-side (undefined ->
      // the Explorer silently dies). Keep the "strip the leading The" logic
      // inlined for exactly that reason. Verify in a browser after editing.
      sortFn: (a, b) => {
        if ((!a.isFolder && !b.isFolder) || (a.isFolder && b.isFolder)) {
          return a.displayName
            .replace(/^the\s+/i, "")
            .localeCompare(b.displayName.replace(/^the\s+/i, ""), undefined, {
              numeric: true,
              sensitivity: "base",
            })
        }
        if (!a.isFolder && b.isFolder) {
          return 1
        } else {
          return -1
        }
      },
    }),
  ],
  right: [
    Component.DesktopOnly(Component.Infobox()),
    // Content-bearing folder-root pages (the nations, the Witherwild: a folder
    // whose index.md is an authored page carrying a `kind`, not an
    // auto-generated listing) get the same graph box as single notes. Bare
    // folder listings and tag pages have no `kind`, so they render no graph.
    Component.ConditionalRender({
      component: Component.Graph(graphConfig),
      condition: (page) => {
        const kind = (page.fileData.frontmatter as Record<string, unknown> | undefined)?.["kind"]
        return typeof kind === "string" && kind.length > 0
      },
    }),
  ],
}
