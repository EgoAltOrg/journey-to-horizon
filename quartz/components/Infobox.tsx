import { JSX } from "preact"
import { QuartzComponent, QuartzComponentConstructor, QuartzComponentProps } from "./types"
import style from "./styles/infobox.scss"
import {
  FilePath,
  FullSlug,
  joinSegments,
  pathToRoot,
  slugifyFilePath,
  transformLink,
} from "../util/path"
import { classNames } from "../util/lang"

// The typed-infobox schema for the article-templates pilot. Field order here
// is render order. Kept in step with the sync whitelist (INFOBOX_KIND_FIELDS
// in scripts/sync-from-ontos.py), the gate (scripts/check-infobox-fields.py),
// and the authoring reference in the Ontos campaign folder.
const KIND_FIELDS: Record<string, string[]> = {
  person: [
    "role",
    "ancestry",
    "culture",
    "pronouns",
    "house",
    "nation",
    "allegiance",
    "born",
    "died",
  ],
  nation: ["capital", "ruler", "government", "founded"],
  location: ["category", "nation", "region", "ruler", "population", "faith"],
  organization: [
    "category",
    "leader",
    "seat",
    "region",
    "allegiance",
    "office",
    "heir",
    "words",
    "relic",
    "founded",
  ],
  "magic-system": ["source", "practitioners"],
  being: ["nature", "domain", "fate"],
  artifact: ["category", "origin", "wielder"],
  event: [
    "category",
    "when",
    "place",
    "parties",
    "commanders",
    "strength",
    "casualties",
    "outcome",
    "part-of",
  ],
  ancestry: ["homeland", "standing"],
}

// Row labels that a plain first-letter capitalization would get wrong.
// `category` is keyed to avoid colliding with the universal bookkeeping
// `type:` field, but reads as "Type" (a church, a house, a guild).
const FIELD_LABELS: Record<string, string> = {
  category: "Type",
  faith: "Dominant faith",
  ruler: "Ruling Power",
  when: "Date",
  "part-of": "Part of",
}

// Fields whose VALUE must render exactly as authored, not title-cased.
// Pronouns are lowercase by convention ("she/her", not "She/her").
const NO_CAPITALIZE = new Set(["pronouns"])

const kindLabel = (kind: string): string =>
  kind
    .split("-")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ")

const fieldLabel = (field: string): string =>
  FIELD_LABELS[field] ?? field.charAt(0).toUpperCase() + field.slice(1)

// Frontmatter values are NOT processed by the CrawlLinks transformer, so a
// wikilink arrives here as a raw string like "[[house-voldis|House Voldis]]".
// Parse that pattern ourselves and resolve it exactly the way the site's own
// body links resolve: transformLink() with the "shortest" strategy (which
// carries this repo's patched folder-index rule, so [[armada]] resolves to
// locations/armada/index.md).
const WIKILINK_RE = /\[\[([^\[\]|#]+)(?:#[^\[\]|]*)?(?:\|([^\[\]]+))?\]\]/g

const targetExists = (target: string, allSlugs: FullSlug[]): boolean => {
  const canonical = slugifyFilePath((target.trim() + ".md") as FilePath)
  return allSlugs.some((slug) => {
    if (slug === canonical) {
      return true
    }
    const parts = slug.split("/")
    const fileName = parts.at(-1)
    if (fileName === "index" && parts.length >= 2) {
      return canonical === parts.at(-2)
    }
    return canonical === fileName
  })
}

const renderString = (
  value: string,
  slug: FullSlug,
  allSlugs: FullSlug[],
): (string | JSX.Element)[] => {
  const parts: (string | JSX.Element)[] = []
  let last = 0
  for (const m of value.matchAll(WIKILINK_RE)) {
    if (m.index! > last) {
      parts.push(value.slice(last, m.index))
    }
    const target = m[1].trim()
    const display = (m[2] ?? m[1]).trim()
    if (targetExists(target, allSlugs)) {
      const href = transformLink(slug, target, { strategy: "shortest", allSlugs })
      parts.push(
        <a href={href} class="internal">
          {display}
        </a>,
      )
    } else {
      // Target page isn't on the public site (or is ambiguous): degrade to
      // plain text rather than emit a dead link.
      parts.push(display)
    }
    last = m.index! + m[0].length
  }
  if (last < value.length) {
    parts.push(value.slice(last))
  }
  return parts
}

// Capitalize the first character of a rendered value so field values always
// read title-style regardless of how they're written in the source
// ("god" -> "God", "central" -> "Central", "angelic being" -> "Angelic
// being"). Only touches the leading plain-text run: a value that starts with
// a wikilink (first part is an <a>) is left alone, since its display text is
// already cased by the author.
const capitalizeFirst = (parts: (string | JSX.Element)[]): (string | JSX.Element)[] => {
  if (parts.length > 0 && typeof parts[0] === "string" && parts[0].length > 0) {
    parts[0] = parts[0].charAt(0).toUpperCase() + parts[0].slice(1)
  }
  return parts
}

const renderValue = (
  value: unknown,
  slug: FullSlug,
  allSlugs: FullSlug[],
  capitalize = true,
): (string | JSX.Element)[] => {
  if (typeof value === "boolean") {
    return [value ? "Yes" : "No"]
  }
  if (Array.isArray(value)) {
    const parts: (string | JSX.Element)[] = []
    value.forEach((item, i) => {
      if (i > 0) {
        parts.push(", ")
      }
      parts.push(...renderValue(item, slug, allSlugs, capitalize))
    })
    return parts
  }
  if (typeof value === "string") {
    const rendered = renderString(value, slug, allSlugs)
    return capitalize ? capitalizeFirst(rendered) : rendered
  }
  return [String(value)]
}

export default (() => {
  const Infobox: QuartzComponent = ({ fileData, displayClass, ctx }: QuartzComponentProps) => {
    const fm = fileData.frontmatter as Record<string, unknown> | undefined
    const kind = fm?.["kind"]
    const validKind = typeof kind === "string" && kind in KIND_FIELDS
    const image = typeof fm?.["image"] === "string" ? (fm["image"] as string) : undefined
    const imageCaption =
      typeof fm?.["image_caption"] === "string" ? (fm["image_caption"] as string) : undefined

    // A card exists when the page has a portrait OR a valid typed kind. An
    // untyped page with no image renders no card, exactly as before.
    if (!image && !validKind) {
      return null
    }

    const rows = validKind
      ? KIND_FIELDS[kind as string]
          .map((field) => [field, fm![field]] as const)
          .filter(([, value]) => value !== undefined && value !== null && value !== "")
      : []

    // `image:` is a bare asset filename resolving to content/assets/. Build a
    // page-relative URL (root-relative would break under the deployed base
    // path), the same relative-URL approach Quartz uses for every internal
    // link, so no base path is ever hardcoded here.
    const imageSrc = image ? joinSegments(pathToRoot(fileData.slug!), "assets", image) : undefined
    const title = typeof fm?.["title"] === "string" ? (fm["title"] as string) : ""

    return (
      <div class={classNames(displayClass, "infobox")}>
        {imageSrc && (
          <figure class="infobox-figure">
            <img class="infobox-image" src={imageSrc} alt={title} />
            {imageCaption && <figcaption class="infobox-caption">{imageCaption}</figcaption>}
          </figure>
        )}
        {validKind && <span class="infobox-kind">{kindLabel(kind as string)}</span>}
        {rows.length > 0 && (
          <dl class="infobox-fields">
            {rows.map(([field, value]) => (
              <>
                <dt>{fieldLabel(field)}</dt>
                <dd>
                  {renderValue(value, fileData.slug!, ctx.allSlugs, !NO_CAPITALIZE.has(field))}
                </dd>
              </>
            ))}
          </dl>
        )}
      </div>
    )
  }

  Infobox.css = style

  return Infobox
}) satisfies QuartzComponentConstructor
