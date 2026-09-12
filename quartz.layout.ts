import { PageLayout, SharedLayout } from "./quartz/cfg"
import * as Component from "./quartz/components"

// This wiki has no force graph (kept deliberately spare and easy to explore),
// so there is no graph config here and the Graph component is mounted nowhere.

// components shared across all pages
export const sharedPageComponents: SharedLayout = {
  head: Component.Head(),
  // Top nav is the primary navigation (this wiki has no Explorer tree), with the
  // EN/PT language switch beside it. Both are language-aware and server-rendered.
  header: [Component.TopNav(), Component.LanguageToggle()],
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
  ],
  right: [
    Component.DesktopOnly(Component.Infobox()),
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
  ],
  right: [
    Component.DesktopOnly(Component.Infobox()),
  ],
}
