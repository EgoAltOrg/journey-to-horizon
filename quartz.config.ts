import { QuartzConfig } from "./quartz/cfg"
import * as Plugin from "./quartz/plugins"

/**
 * Quartz 4 Configuration
 *
 * See https://quartz.jzhao.xyz/configuration for more information.
 */
const config: QuartzConfig = {
  configuration: {
    // CHANGE per wiki: pageTitle is the site name, baseUrl is
    // egoaltorg.github.io/<your-repo> (used for RSS, sitemap, and OG tags).
    pageTitle: "Wiki",
    pageTitleSuffix: "",
    enableSPA: true,
    enablePopovers: true,
    analytics: null,
    locale: "en-US",
    baseUrl: "egoaltorg.github.io/CHANGE-ME",
    ignorePatterns: ["private", "templates", ".obsidian"],
    defaultDateType: "modified",
    theme: {
      fontOrigin: "googleFonts",
      cdnCaching: true,
      typography: {
        header: "Schibsted Grotesk",
        body: "Source Sans Pro",
        code: "IBM Plex Mono",
      },
      colors: {
        // Default theme (a warm parchment day / ember night). Replace both
        // palettes per wiki, e.g. derived from the campaign's key art.
        lightMode: {
          light: "#f8f2e7",
          lightgray: "#e2d8c8",
          gray: "#a99b88",
          darkgray: "#4a3f38",
          dark: "#2c2320",
          secondary: "#a34a1f",
          tertiary: "#c96c3b",
          highlight: "rgba(163, 74, 31, 0.10)",
          textHighlight: "#f0913a55",
        },
        darkMode: {
          light: "#140f11",
          lightgray: "#3a2b27",
          gray: "#8a7466",
          darkgray: "#d8cec2",
          dark: "#f0e8da",
          secondary: "#f0913a",
          tertiary: "#c96c3b",
          highlight: "rgba(240, 145, 58, 0.12)",
          textHighlight: "#f0913a44",
        },
      },
    },
  },
  plugins: {
    transformers: [
      Plugin.FrontMatter(),
      Plugin.CreatedModifiedDate({
        priority: ["frontmatter", "git", "filesystem"],
      }),
      Plugin.SyntaxHighlighting({
        theme: {
          light: "github-light",
          dark: "github-dark",
        },
        keepBackground: false,
      }),
      Plugin.ObsidianFlavoredMarkdown({ enableInHtmlEmbed: false }),
      Plugin.GitHubFlavoredMarkdown(),
      Plugin.TableOfContents(),
      Plugin.CrawlLinks({ markdownLinkResolution: "shortest" }),
      Plugin.Description(),
      Plugin.Latex({ renderEngine: "katex" }),
      Plugin.LeafletMap({ enableCopyTool: true }),
    ],
    filters: [Plugin.RemoveDrafts()],
    emitters: [
      Plugin.AliasRedirects(),
      Plugin.ComponentResources(),
      Plugin.ContentPage(),
      Plugin.FolderPage(),
      Plugin.TagPage(),
      Plugin.ContentIndex({
        enableSiteMap: true,
        enableRSS: true,
      }),
      Plugin.Assets(),
      Plugin.Static(),
      Plugin.Favicon(),
      Plugin.NotFoundPage(),
      // Comment out CustomOgImages to speed up build time
      Plugin.CustomOgImages(),
    ],
  },
}

export default config
