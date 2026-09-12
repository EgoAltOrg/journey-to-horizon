import { QuartzComponent, QuartzComponentConstructor, QuartzComponentProps } from "./types"
import { resolveRelative, simplifySlug, FullSlug } from "../util/path"
import { classNames } from "../util/lang"

// Primary navigation for a concise, top-nav-driven wiki (no Explorer tree).
// Each entry is language-aware: on an English page it links to the English slug
// with the English label; on a Portuguese page (slug under pt/) it links into
// the parallel /pt/ subtree with the Portuguese label. Server-rendered per page,
// so following a nav link keeps the reader in their current language with no
// client-side state. Edit this list to match the wiki's real top-level pages.
const NAV = [
  { slug: "index", en: "Home", pt: "Início" },
  { slug: "map", en: "Map", pt: "Mapa" },
  { slug: "world", en: "World", pt: "Mundo" },
  { slug: "terranamancy", en: "Terranamancy", pt: "Terranamância" },
  { slug: "house-rules", en: "House Rules", pt: "Regras" },
  { slug: "gazetteer", en: "Gazetteer", pt: "Gazetteer" },
]

const TopNav: QuartzComponent = ({ fileData, displayClass }: QuartzComponentProps) => {
  const slug = fileData.slug ?? ""
  const isPt = slug === "pt" || slug.startsWith("pt/")
  const neutral = isPt ? (slug === "pt" ? "index" : slug.slice(3) || "index") : slug
  return (
    <nav class={classNames(displayClass, "topnav")} aria-label="primary">
      {NAV.map((item) => {
        const target = (isPt ? `pt/${item.slug}` : item.slug) as FullSlug
        const href = resolveRelative(fileData.slug!, simplifySlug(target))
        return (
          <a href={href} class={item.slug === neutral ? "active" : ""}>
            {isPt ? item.pt : item.en}
          </a>
        )
      })}
    </nav>
  )
}

TopNav.css = `
.topnav {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem 1.1rem;
  align-items: center;
  margin: 0 0 0.6rem 0;
  font-family: var(--titleFont);
  font-size: 1rem;
}
.topnav a {
  color: var(--darkgray);
  text-decoration: none;
  padding: 0.15rem 0;
  border-bottom: 2px solid transparent;
}
.topnav a:hover {
  color: var(--secondary);
}
.topnav a.active {
  color: var(--secondary);
  border-bottom-color: var(--secondary);
}
`

export default (() => TopNav) satisfies QuartzComponentConstructor
