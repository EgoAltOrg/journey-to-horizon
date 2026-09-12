import { QuartzComponent, QuartzComponentConstructor, QuartzComponentProps } from "./types"
import { resolveRelative, simplifySlug, FullSlug } from "../util/path"
import { classNames } from "../util/lang"

// EN | PT switch. Every page has a counterpart in the other language (English at
// the slug, Portuguese under the parallel /pt/ subtree), so this links the
// current page to its counterpart, keeping the reader on the same page in the
// other language. Server-rendered per page: no client-side state needed.
const LanguageToggle: QuartzComponent = ({ fileData, displayClass }: QuartzComponentProps) => {
  const slug = fileData.slug ?? ""
  const isPt = slug === "pt" || slug.startsWith("pt/")
  const neutral = isPt ? (slug === "pt" ? "index" : slug.slice(3) || "index") : slug
  const enHref = resolveRelative(fileData.slug!, simplifySlug(neutral as FullSlug))
  const ptHref = resolveRelative(fileData.slug!, simplifySlug(`pt/${neutral}` as FullSlug))
  return (
    <div class={classNames(displayClass, "langtoggle")}>
      <a href={enHref} class={!isPt ? "active" : ""} aria-label="English">
        EN
      </a>
      <span class="sep" aria-hidden="true">
        ·
      </span>
      <a href={ptHref} class={isPt ? "active" : ""} aria-label="Português">
        PT
      </a>
    </div>
  )
}

LanguageToggle.css = `
.langtoggle {
  display: flex;
  gap: 0.4rem;
  align-items: center;
  font-size: 0.85rem;
  font-weight: 600;
}
.langtoggle a {
  color: var(--gray);
  text-decoration: none;
}
.langtoggle a.active {
  color: var(--secondary);
}
.langtoggle .sep {
  color: var(--lightgray);
}
`

export default (() => LanguageToggle) satisfies QuartzComponentConstructor
