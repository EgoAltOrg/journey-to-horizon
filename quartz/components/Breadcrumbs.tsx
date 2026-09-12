import { QuartzComponent, QuartzComponentConstructor, QuartzComponentProps } from "./types"
import breadcrumbsStyle from "./styles/breadcrumbs.scss"
import { FullSlug, SimpleSlug, resolveRelative, simplifySlug } from "../util/path"
import { classNames } from "../util/lang"
import { trieFromAllFiles } from "../util/ctx"

type CrumbData = {
  displayName: string
  path: string
}

interface BreadcrumbOptions {
  /**
   * Symbol between crumbs
   */
  spacerSymbol: string
  /**
   * Name of first crumb
   */
  rootName: string
  /**
   * Name of first crumb on Portuguese pages (slug under pt/). The wiki is
   * bilingual with a parallel /pt/ subtree, so the root crumb is localized.
   */
  rootNamePt: string
  /**
   * Whether to look up frontmatter title for folders (could cause performance problems with big vaults)
   */
  resolveFrontmatterTitle: boolean
  /**
   * Whether to display the current page in the breadcrumbs.
   */
  showCurrentPage: boolean
}

const defaultOptions: BreadcrumbOptions = {
  spacerSymbol: "❯",
  rootName: "Home",
  rootNamePt: "Início",
  resolveFrontmatterTitle: true,
  showCurrentPage: true,
}

function formatCrumb(displayName: string, baseSlug: FullSlug, currentSlug: SimpleSlug): CrumbData {
  return {
    displayName: displayName.replaceAll("-", " "),
    path: resolveRelative(baseSlug, currentSlug),
  }
}

export default ((opts?: Partial<BreadcrumbOptions>) => {
  const options: BreadcrumbOptions = { ...defaultOptions, ...opts }
  const Breadcrumbs: QuartzComponent = ({
    fileData,
    allFiles,
    displayClass,
    ctx,
  }: QuartzComponentProps) => {
    const trie = (ctx.trie ??= trieFromAllFiles(allFiles))
    const slug = fileData.slug ?? ""
    const isPt = slug === "pt" || slug.startsWith("pt/")
    const slugParts = slug.split("/")
    const pathNodes = trie.ancestryChain(slugParts)

    if (!pathNodes) {
      return null
    }

    let crumbs: CrumbData[] = pathNodes.map((node, idx) => {
      const crumb = formatCrumb(node.displayName, fileData.slug!, simplifySlug(node.slug))
      // For last node (current page), set empty path
      if (idx === pathNodes.length - 1) {
        crumb.path = ""
      }
      return crumb
    })

    if (isPt) {
      // On a Portuguese page the ancestry chain is [site root, pt folder, page].
      // Drop the English site-root crumb and localize the /pt/ root, so the trail
      // reads "Início ❯ Page" instead of "Home ❯ pt ❯ Page".
      crumbs = crumbs.slice(1)
      if (crumbs.length > 0) {
        crumbs[0].displayName = options.rootNamePt
      }
    } else if (crumbs.length > 0) {
      crumbs[0].displayName = options.rootName
    }

    if (!options.showCurrentPage) {
      crumbs.pop()
    }

    return (
      <nav class={classNames(displayClass, "breadcrumb-container")} aria-label="breadcrumbs">
        {crumbs.map((crumb, index) => (
          <div class="breadcrumb-element">
            <a href={crumb.path}>{crumb.displayName}</a>
            {index !== crumbs.length - 1 && <p>{` ${options.spacerSymbol} `}</p>}
          </div>
        ))}
      </nav>
    )
  }
  Breadcrumbs.css = breadcrumbsStyle

  return Breadcrumbs
}) satisfies QuartzComponentConstructor
