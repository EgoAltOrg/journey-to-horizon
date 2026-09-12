import { QuartzConfig } from "./quartz/cfg"
import * as Plugin from "./quartz/plugins"

/**
 * Quartz 4 Configuration
 *
 * See https://quartz.jzhao.xyz/configuration for more information.
 */
const config: QuartzConfig = {
  configuration: {
    pageTitle: "Journey to Horizon",
    pageTitleSuffix: "",
    enableSPA: true,
    enablePopovers: true,
    analytics: null,
    locale: "en-US",
    baseUrl: "egoaltorg.github.io/journey-to-horizon",
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
        // Journey to Horizon theme, from the campaign frame art: sea-mist day /
        // deep-ocean night, teal and cyan with warm gold accents.
        lightMode: {
          light: "#f1f5f6",
          lightgray: "#d6e0e2",
          gray: "#849aa0",
          darkgray: "#2b3a42",
          dark: "#12314f",
          secondary: "#1d6f86",
          tertiary: "#c0883a",
          highlight: "rgba(29, 111, 134, 0.10)",
          textHighlight: "#d8b14f55",
        },
        darkMode: {
          light: "#0f1720",
          lightgray: "#26333d",
          gray: "#6f878f",
          darkgray: "#cdd8dd",
          dark: "#eaf2f5",
          secondary: "#37b4d4",
          tertiary: "#d8b14f",
          highlight: "rgba(55, 180, 212, 0.12)",
          textHighlight: "#d8b14f44",
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
