import { Root } from "mdast"
import { QuartzTransformerPlugin } from "../types"
import { visit } from "unist-util-visit"
import { Node, Parent } from "unist"
import { VFile } from "vfile"
import { Element } from "hast"
import { load } from "js-yaml"
import { BuildCtx } from "../../util/ctx"
import { FilePath, FullSlug, resolveRelative, transformLink } from "../../util/path"

/**
 * TYPES.TS
 */

type Wiki = string[][] // Wiki links take the shape of string[][]
type Coordinates = `${number}, ${number}`
type Hex = `#${string}`

interface MarkerObject {
  mapName?: string
  coordinates: Coordinates
  icon?: string
  colour?: Hex
  minZoom?: number
  category?: string
}

interface MapObject {
  name?: string
  image: string | Wiki
  height?: number
  minZoom?: number
  maxZoom?: number
  defaultZoom?: number
  zoomDelta?: number
  scale?: number
  unit?: string
}

// A page-level `submap:` frontmatter block: the page gets its own embedded
// Leaflet map (same component as the main map, parameterized by image +
// local markers). `caption` renders player-visibly on the map itself (as
// the attribution line), used to flag placeholder art. `markers` is a list
// of local pins in THIS image's own pixel coordinate space; local pin
// coordinates do not survive a swap of `image:` for different art.
interface SubmapObject {
  image: string | Wiki
  caption?: string
  height?: number
  minZoom?: number
  maxZoom?: number
  defaultZoom?: number
  zoomDelta?: number
  scale?: number
  unit?: string
  markers?: unknown
}

type ValidatorFunction<T> = (value: unknown) => value is T

interface LeafletMapPluginOptions {
  enableCopyTool?: boolean
}

/**
 * CONSTANTS.TS
 */

// The single source of truth for the marker category vocabulary. A marker
// whose `category:` is missing or not in this list lands in the default
// layer group, which always renders and never appears in the toggle control.
const MARKER_CATEGORIES = ["settlement", "holy-site", "landmark", "nation"] as const
type MarkerCategory = (typeof MARKER_CATEGORIES)[number]

// Data stored across several invocations of this plugin
const LEAFLET_MAP_PLUGIN_DATA: {
  markerMap: { [key: string]: MarkerEntry[] }
  // Slugs of pages whose frontmatter declares a `submap:` block. Filled
  // during the markdown pass (which completes for every file before any
  // HTML pass runs, the same ordering markerMap already relies on), then
  // read while building marker elements so a main-map pin whose target
  // page has a local map gets a drill-down popup. The CONTENT declares,
  // the plugin discovers; no page names are hardcoded here.
  submapSlugs: Set<string>
} = {
  markerMap: {
    notDefinedMap: [],
  },
  submapSlugs: new Set(),
}

const C = {
  regExp: {
    hexColourValidation: /([0-9A-F]{3}){1,2}$/i,
    coordinatesValidation: /[0-9]+\s*,\s*[0-9]+/,
    iconValidation: /([a-z]+:)?[a-z]+([\-][a-z]+)*/,
    url: /https?:/,
    arrayString: /^\[.*[\]]$/,
  },
  map: {
    default: {
      minZoom: 0,
      maxZoom: 2,
      zoomDelta: 0.5,
      zoomSnap: 0.01,
      height: 600,
      scale: 1,
      unit: "",
    },
  },
  marker: {
    default: {
      colour: "#21409a",
      icon: "circle-small",
    },
  },
  versions: {
    leaflet: "1.9.4/dist/leaflet.js",
    lucide: "0.575.0",
  },
} as const

/**
 * UTIL.TS
 */

function isNonEmptyObject(value: unknown): value is { [key: string]: unknown } {
  if (!value || typeof value !== "object") return false
  return Object.keys(value).length > 0
}

function isNotNull<T>(value: T | null): value is T {
  return value !== null
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max)
}

function cleanSource(source: string | Wiki): string {
  if (typeof source === "string") return source
  return source.toString().replaceAll("[", "").replaceAll("]", "")
}

/**
 * VALIDATORS.TS
 */

type ValidatedProperties = string | Wiki | number

function stringValidator(value: unknown): value is string {
  return typeof value === "string"
}

function sourcevalidator(value: unknown): value is string | Wiki {
  if (stringValidator(value)) return value.length > 0
  if (Array.isArray(value) && Array.isArray(value[0]) && stringValidator(value[0][0]))
    return value[0][0].length > 0
  return false
}

function numberValidator(value: unknown): value is number {
  return typeof value === "number" && isFinite(value) && !isNaN(value)
}

function positiveNumberValidator(value: unknown): value is number {
  return numberValidator(value) && value > 0
}

function coordinatesValidator(value: unknown): value is Coordinates {
  return typeof value === "string" && C.regExp.coordinatesValidation.test(value)
}

function iconValidator(value: unknown): value is string {
  return typeof value === "string" && C.regExp.iconValidation.test(value)
}

function colourValidator(value: unknown): value is Hex {
  return typeof value === "string" && C.regExp.hexColourValidation.test(value)
}

function categoryValidator(value: unknown): value is MarkerCategory {
  return typeof value === "string" && (MARKER_CATEGORIES as readonly string[]).includes(value)
}

const Validator = {
  string: stringValidator,
  source: sourcevalidator,
  number: numberValidator,
  positiveNumber: positiveNumberValidator,
  coordinates: coordinatesValidator,
  icon: iconValidator,
  colour: colourValidator,
} as const satisfies Record<string, ValidatorFunction<ValidatedProperties>>

/**
 * SCHEMAS.TS
 */

type Schema<T extends string> = Record<
  T,
  { validator: ValidatorFunction<unknown>; required?: boolean }
>
type ValidatedSchemas = MarkerObject | MapObject | SubmapObject

const markerSchema: Schema<keyof MarkerObject> = {
  mapName: { validator: Validator.string },
  coordinates: { validator: Validator.coordinates, required: true },
  icon: { validator: Validator.icon },
  colour: { validator: Validator.colour },
  minZoom: { validator: Validator.number },
  // Deliberately lenient (any string): an out-of-vocabulary category must
  // never make a pin vanish. Normalisation to the vocabulary happens in
  // buildMarkerElement via categoryValidator.
  category: { validator: Validator.string },
}
const mapSchema: Schema<keyof MapObject> = {
  name: { validator: Validator.string },
  image: { validator: Validator.source, required: true },
  height: { validator: Validator.positiveNumber },
  minZoom: { validator: Validator.number },
  maxZoom: { validator: Validator.number },
  defaultZoom: { validator: Validator.number },
  zoomDelta: { validator: Validator.positiveNumber },
  scale: { validator: Validator.positiveNumber },
  unit: { validator: Validator.string },
}
// `markers` is validated per-entry in buildSubmapElement, not here (the
// schema factory only handles scalar-ish properties).
const submapSchema: Schema<Exclude<keyof SubmapObject, "markers">> = {
  image: { validator: Validator.source, required: true },
  caption: { validator: Validator.string },
  height: { validator: Validator.positiveNumber },
  minZoom: { validator: Validator.number },
  maxZoom: { validator: Validator.number },
  defaultZoom: { validator: Validator.number },
  zoomDelta: { validator: Validator.positiveNumber },
  scale: { validator: Validator.positiveNumber },
  unit: { validator: Validator.string },
}

function schemaValidatorFactory<T extends ValidatedSchemas>(
  schema: Schema<string>,
): ValidatorFunction<T> {
  function schemaValidator(value: unknown): value is T {
    if (!isNonEmptyObject(value)) return false

    return Object.entries(schema)
      .map(([key, validate]) => {
        return (value[key] === undefined && !validate.required) || validate.validator(value[key])
      })
      .every(Boolean)
  }
  return schemaValidator
}

export const SchemaValidator = {
  marker: schemaValidatorFactory<MarkerObject>(markerSchema),
  map: schemaValidatorFactory<MapObject>(mapSchema),
  submap: schemaValidatorFactory<SubmapObject>(submapSchema),
} as const satisfies Record<string, ValidatorFunction<ValidatedSchemas>>

/**
 * MARKER.TS
 */

interface MarkerEntry extends MarkerObject {
  name: string
  link: FullSlug
  // True for a pin declared inside a `submap:` block (local to that map),
  // as opposed to one collected from a page's `marker:` block.
  local?: boolean
}

function isProperEntry(entry: unknown): entry is { [key: string]: string | number } {
  if (!isNonEmptyObject(entry)) return false
  return Object.values(entry).every(
    (property) => typeof property === "string" || typeof property === "number",
  )
}

function parseMarkerFromEntry(entry: unknown, name: string, link: FullSlug): MarkerEntry | null {
  if (!isProperEntry(entry)) return null
  if (!SchemaValidator.marker(entry)) return null
  return {
    ...entry,
    name,
    link,
  }
}

function buildMarkerData(file: VFile): void {
  const { slug, frontmatter } = file.data
  const markerData = frontmatter?.marker

  if (!slug || !frontmatter || !frontmatter?.title || !markerData || !Array.isArray(markerData)) {
    return
  }

  markerData
    .map((entry) => parseMarkerFromEntry(entry, frontmatter.title, slug))
    .filter(isNotNull)
    .forEach((marker) => {
      const mapName = marker.mapName

      if (!mapName) {
        LEAFLET_MAP_PLUGIN_DATA.markerMap["notDefinedMap"]?.push(marker)
        return
      }

      if (LEAFLET_MAP_PLUGIN_DATA.markerMap[mapName] === undefined) {
        LEAFLET_MAP_PLUGIN_DATA.markerMap[mapName] = []
      }

      LEAFLET_MAP_PLUGIN_DATA.markerMap[mapName]?.push(marker)
    })
}

function recordSubmapDeclaration(file: VFile): void {
  const { slug, frontmatter } = file.data
  if (!slug || !frontmatter) return
  if (SchemaValidator.submap(frontmatter.submap)) {
    LEAFLET_MAP_PLUGIN_DATA.submapSlugs.add(slug)
  }
}

function buildMarkerElement(
  marker: MarkerEntry,
  currentSlug: FullSlug,
  mapMinZoom: number,
): Element {
  // Only vocabulary categories reach the client; anything else is treated
  // as uncategorised so the pin still renders (in the default group).
  const category = categoryValidator(marker.category) ? marker.category : undefined
  // `data-submap` marks a pin whose target page has its own local map. It
  // is emitted but no longer changes click behaviour: 2026-07-17 the extra
  // popup was dropped (it added a pointless second click while local maps
  // are placeholder art), so every pin now navigates straight to its page,
  // which already embeds its local map. Kept on the element so drill-down
  // affordances can be reinstated once real local cartography exists.
  const hasSubmap = !marker.local && LEAFLET_MAP_PLUGIN_DATA.submapSlugs.has(marker.link as string)
  return {
    type: "element",
    tagName: "div",
    properties: {
      class: ["leaflet-marker"],
      "data-name": marker.name,
      // A local submap pin's link is already a final href (the map
      // anchor by default), never a slug to resolve.
      "data-link":
        marker.local || /https?:/.test(marker.link)
          ? marker.link
          : resolveRelative(currentSlug, marker.link as FullSlug),
      "data-coordinates": marker.coordinates,
      "data-icon": (marker.icon ?? C.marker.default.icon).replace("lucide-", ""),
      "data-colour": marker.colour ?? C.marker.default.colour,
      "data-min-zoom": marker.minZoom ?? mapMinZoom,
      ...(category !== undefined ? { "data-category": category } : {}),
      ...(hasSubmap ? { "data-submap": "true" } : {}),
    },
    children: [],
  }
}

declare module "vfile" {
  interface DataMap {
    slug: FullSlug
    filePath: FilePath
    relativePath: FilePath
    frontmatter: { [key: string]: unknown } & { title: string } & Partial<{
        tags: string[]
        aliases: string[]
        modified: string
        created: string
        published: string
        description: string
        socialDescription: string
        publish: boolean | string
        draft: boolean | string
        lang: string
        enableToc: string
        cssclasses: string[]
        socialImage: string
        comments: boolean | string
      }>
  }
}

/**
 * MAP.TS
 */

type ExtendedNode = Node & {
  value?: string
  children?: Node[]
  properties?: { [key: string]: string }
}

function source(node: ExtendedNode): string {
  if (node.type === "text" && node.value !== undefined) return node.value
  if (node.children === undefined) return ""

  return node.children.map((child) => source(child)).join("")
}

function parseMapFromNode(node: ExtendedNode): MapObject | undefined {
  const entry: unknown = load(source(node))
  if (!isNonEmptyObject(entry) || !Array.isArray(entry.views)) return
  return entry.views
    .map((view) => {
      if (!isProperEntry(view)) return null
      // Confirm we are working with the right type of base
      if (!view.type || view.type !== "leaflet-map") return null

      const object = {
        name: view.mapName,
        image: view.image,
        height: view.height,
        minZoom: view.minZoom,
        maxZoom: view.maxZoom,
        defaultZoom: view.defaultZoom,
        zoomDelta: view.zoomDelta,
        scale: parseFloat((view.scale ?? "").toString()),
        unit: view.unit,
      }

      if (!SchemaValidator.map(object)) return null
      return object
    })
    .filter(isNotNull)
    .at(0)
}

// Shared between the main map (a ```base codeblock) and page-level submaps
// (a `submap:` frontmatter block): both render the same div.leaflet-map
// component, so the client script needs exactly one code path.
function buildLeafletContainer(
  options: LeafletMapPluginOptions,
  mapData: MapObject | SubmapObject,
  mapSource: string,
  markers: MarkerEntry[],
  currentSlug: FullSlug,
  caption?: string,
): Element {
  const minZoom = mapData.minZoom ?? C.map.default.minZoom
  const maxZoom = Math.max(mapData.maxZoom ?? C.map.default.maxZoom, minZoom)

  return {
    type: "element",
    tagName: "div",
    properties: {
      class: ["leaflet-map"],
      "data-src": mapSource,
      "data-height": mapData.height ?? C.map.default.height,
      "data-min-zoom": minZoom,
      "data-max-zoom": maxZoom,
      "data-default-zoom": clamp(mapData.defaultZoom ?? minZoom, minZoom, maxZoom),
      "data-zoom-delta": mapData.zoomDelta ?? C.map.default.zoomDelta,
      "data-scale": mapData.scale ?? C.map.default.scale,
      "data-unit": mapData.unit ?? C.map.default.unit,
      "data-enable-copy-tool": options.enableCopyTool ?? false,
      ...(caption !== undefined ? { "data-caption": caption } : {}),
    },
    children: markers.map((marker) => buildMarkerElement(marker, currentSlug, minZoom)),
  }
}

function buildMapData(
  ctx: BuildCtx,
  options: LeafletMapPluginOptions,
  file: VFile,
  node: ExtendedNode,
): Element | undefined {
  const mapData = parseMapFromNode(node)
  if (!mapData) return

  const currentSlug = file.data.slug
  if (!currentSlug) throw new Error(`${file.path} has no slug`)
  const mapSource = transformLink(currentSlug, cleanSource(mapData.image), {
    strategy: "shortest",
    allSlugs: ctx.allSlugs,
  })

  const undefinedMarkers = LEAFLET_MAP_PLUGIN_DATA.markerMap["notDefinedMap"] ?? []
  const definedMarkers = mapData.name ? (LEAFLET_MAP_PLUGIN_DATA.markerMap[mapData.name] ?? []) : []
  const markers = [...undefinedMarkers, ...definedMarkers]

  return {
    type: "element",
    tagName: "div",
    properties: {},
    children: [buildLeafletContainer(options, mapData, mapSource, markers, currentSlug)],
  }
}

/**
 * SUBMAP.TS
 */

// Anchor id for the embedded local map, so the main map's "Open local map"
// popup link can jump straight to it.
const SUBMAP_ANCHOR_ID = "local-map"

// A submap's own pins are declared inline in the block (name + coordinates,
// plus the usual optional marker fields). `link` defaults to the map anchor
// itself so a purely decorative "you are here" pin navigates nowhere new.
function parseLocalMarker(entry: unknown, anchorLink: string): MarkerEntry | null {
  if (!isProperEntry(entry)) return null
  if (!Validator.string(entry.name) || entry.name.length === 0) return null
  if (!SchemaValidator.marker(entry)) return null
  return {
    ...entry,
    name: entry.name,
    link: (Validator.string(entry.link) ? entry.link : anchorLink) as FullSlug,
    local: true,
  }
}

function buildSubmapElement(
  ctx: BuildCtx,
  options: LeafletMapPluginOptions,
  file: VFile,
): Element | undefined {
  const submap = file.data.frontmatter?.submap
  if (!SchemaValidator.submap(submap)) return

  const currentSlug = file.data.slug
  if (!currentSlug) throw new Error(`${file.path} has no slug`)
  const mapSource = transformLink(currentSlug, cleanSource(submap.image), {
    strategy: "shortest",
    allSlugs: ctx.allSlugs,
  })

  const anchorLink = `#${SUBMAP_ANCHOR_ID}`
  const markers = (Array.isArray(submap.markers) ? submap.markers : [])
    .map((entry) => parseLocalMarker(entry, anchorLink))
    .filter(isNotNull)

  return {
    type: "element",
    tagName: "div",
    properties: { id: SUBMAP_ANCHOR_ID },
    children: [
      buildLeafletContainer(options, submap, mapSource, markers, currentSlug, submap.caption),
    ],
  }
}

function transformMapElement(
  ctx: BuildCtx,
  options: LeafletMapPluginOptions,
  tree: Root,
  file: VFile,
): void {
  visit(
    tree,
    { tagName: "code" },
    (node: ExtendedNode, index: number | undefined, parent: Parent | undefined) => {
      if (node.properties?.dataLanguage !== "base" || !parent || index === undefined) {
        return
      }

      const leafletElement = buildMapData(ctx, options, file, node)
      if (!leafletElement) return

      // Replace the codeblock with the leaflet element
      parent.children[index] = leafletElement
    },
  )

  // A page declaring a `submap:` frontmatter block gets its local map
  // appended after the page body.
  const submapElement = buildSubmapElement(ctx, options, file)
  if (submapElement) {
    ;(tree as unknown as Parent).children.push(submapElement)
  }
}

/**
 * CORE.TS
 */

export const LeafletMap: QuartzTransformerPlugin<LeafletMapPluginOptions> = (options) => ({
  name: "LeafletMapPlugin",
  markdownPlugins() {
    return [
      () => {
        // For every file, check if the frontmatter contains marker data,
        // and if so add it to a global constant. Also record which
        // pages declare a `submap:` so main-map pins can offer a
        // drill-down link.
        return (_tree: Root, file: VFile) => {
          buildMarkerData(file)
          recordSubmapDeclaration(file)
        }
      },
    ]
  },
  htmlPlugins(ctx) {
    return [
      () => {
        return (tree: Root, file: VFile) => transformMapElement(ctx, options ?? {}, tree, file)
      },
    ]
  },
  externalResources() {
    return {
      css: [
        {
          inline: true,
          content: `.leaflet-map{width:100%;margin:0;z-index:0;background-color:#5078b41a}.leaflet-map .leaflet-image-layer{margin:0!important}.leaflet-control-button{background:var(--lightgray)}.leaflet-marker-icon a,.leaflet-marker-icon .leaflet-marker-pin{position:absolute;width:32px;height:48px;margin:0 auto;z-index:inherit}.leaflet-marker-icon .leaflet-marker-inner-icon{position:absolute;width:32px;height:19px;font-size:19px;top:8px;left:0;z-index:inherit;margin:0 auto;display:flex;align-items:center;justify-content:center;color:#ebebec}.leaflet-map-property-tag-list{margin:0!important;padding:2px;gap:.3rem;display:flex;color:#ebebec}.leaflet-map-property-tag-item{display:flex;cursor:pointer;padding:0!important;margin:0!important;background:#353535;border-radius:8px;align-items:center;justify-content:space-between}.leaflet-map-property-tag-item-icon{display:flex;justify-content:center;align-items:center;padding:0 .3rem}.leaflet-map-property-tag-item-text{font-size:var(--tag-size);white-space:nowrap}.leaflet-map-property-tag-item-close{display:flex;cursor:pointer;margin-left:.3rem;aspect-ratio:1;justify-content:center;align-items:center;padding:4px;border-radius:8px;color:#ebebec;background:inherit}.leaflet-map-property-tag-item-close:hover{background:#818181b1}.leaflet-map-property-add-item{display:flex;cursor:pointer;aspect-ratio:1;justify-content:center;align-items:center;padding:4px;margin:0!important;border-radius:8px;color:#ebebec;background:#454545}.leaflet-map-property-add-item:hover{background:#818181d0}.leaflet-pane,.leaflet-tile,.leaflet-marker-icon,.leaflet-marker-shadow,.leaflet-tile-container,.leaflet-pane>svg,.leaflet-pane>canvas,.leaflet-zoom-box,.leaflet-image-layer,.leaflet-layer{position:absolute;left:0;top:0}.leaflet-container{overflow:hidden}.leaflet-tile,.leaflet-marker-icon,.leaflet-marker-shadow{-webkit-user-select:none;-moz-user-select:none;user-select:none;-webkit-user-drag:none}.leaflet-tile::selection{background:transparent}.leaflet-safari .leaflet-tile{image-rendering:-webkit-optimize-contrast}.leaflet-safari .leaflet-tile-container{width:1600px;height:1600px;-webkit-transform-origin:0 0;transform-origin:0 0}.leaflet-marker-icon,.leaflet-marker-shadow{display:block}.leaflet-container .leaflet-overlay-pane svg{max-width:none!important;max-height:none!important}.leaflet-container .leaflet-marker-pane img,.leaflet-container .leaflet-shadow-pane img,.leaflet-container .leaflet-tile-pane img,.leaflet-container img.leaflet-image-layer,.leaflet-container .leaflet-tile{max-width:none!important;max-height:none!important;width:auto;padding:0}.leaflet-container img.leaflet-tile{mix-blend-mode:plus-lighter}.leaflet-container.leaflet-touch-zoom{-ms-touch-action:pan-x pan-y;touch-action:pan-x pan-y}.leaflet-container.leaflet-touch-drag{-ms-touch-action:pinch-zoom;touch-action:none;touch-action:pinch-zoom}.leaflet-container.leaflet-touch-drag.leaflet-touch-zoom{-ms-touch-action:none;touch-action:none}.leaflet-container{-webkit-tap-highlight-color:transparent}.leaflet-container a{-webkit-tap-highlight-color:rgba(51,181,229,.4)}.leaflet-tile{filter:inherit;visibility:hidden}.leaflet-tile-loaded{visibility:inherit}.leaflet-zoom-box{width:0;height:0;-moz-box-sizing:border-box;box-sizing:border-box;z-index:800}.leaflet-overlay-pane svg{-moz-user-select:none;user-select:none}.leaflet-pane{z-index:400}.leaflet-tile-pane{z-index:200}.leaflet-overlay-pane{z-index:400}.leaflet-shadow-pane{z-index:500}.leaflet-marker-pane{z-index:600}.leaflet-tooltip-pane{z-index:650}.leaflet-popup-pane{z-index:700}.leaflet-map-pane canvas{z-index:100}.leaflet-map-pane svg{z-index:200}.leaflet-vml-shape{width:1px;height:1px}.lvml{behavior:url(#default#VML);display:inline-block;position:absolute}.leaflet-control{position:relative;z-index:800;pointer-events:visiblePainted;pointer-events:auto}.leaflet-top,.leaflet-bottom{position:absolute;z-index:1000;pointer-events:none}.leaflet-top{top:0}.leaflet-right{right:0}.leaflet-bottom{bottom:0}.leaflet-left{left:0}.leaflet-control{float:left;clear:both}.leaflet-right .leaflet-control{float:right}.leaflet-top .leaflet-control{margin-top:10px}.leaflet-bottom .leaflet-control{margin-bottom:10px}.leaflet-left .leaflet-control{margin-left:10px}.leaflet-right .leaflet-control{margin-right:10px}.leaflet-fade-anim .leaflet-popup{opacity:0;-webkit-transition:opacity .2s linear;-moz-transition:opacity .2s linear;transition:opacity .2s linear}.leaflet-fade-anim .leaflet-map-pane .leaflet-popup{opacity:1}.leaflet-zoom-animated{-webkit-transform-origin:0 0;-ms-transform-origin:0 0;transform-origin:0 0}svg.leaflet-zoom-animated{will-change:transform}.leaflet-zoom-anim .leaflet-zoom-animated{-webkit-transition:-webkit-transform .25s cubic-bezier(0,0,.25,1);-moz-transition:-moz-transform .25s cubic-bezier(0,0,.25,1);transition:transform .25s cubic-bezier(0,0,.25,1)}.leaflet-zoom-anim .leaflet-tile,.leaflet-pan-anim .leaflet-tile{-webkit-transition:none;-moz-transition:none;transition:none}.leaflet-zoom-anim .leaflet-zoom-hide{visibility:hidden}.leaflet-interactive{cursor:pointer}.leaflet-grab{cursor:-webkit-grab;cursor:-moz-grab;cursor:grab}.leaflet-crosshair,.leaflet-crosshair .leaflet-interactive{cursor:crosshair}.leaflet-popup-pane,.leaflet-control{cursor:auto}.leaflet-dragging .leaflet-grab,.leaflet-dragging .leaflet-grab .leaflet-interactive,.leaflet-dragging .leaflet-marker-draggable{cursor:move;cursor:-webkit-grabbing;cursor:-moz-grabbing;cursor:grabbing}.leaflet-marker-icon,.leaflet-marker-shadow,.leaflet-image-layer,.leaflet-pane>svg path,.leaflet-tile-container{pointer-events:none}.leaflet-marker-icon.leaflet-interactive,.leaflet-image-layer.leaflet-interactive,.leaflet-pane>svg path.leaflet-interactive,svg.leaflet-image-layer.leaflet-interactive path{pointer-events:visiblePainted;pointer-events:auto}.leaflet-container{background:var(--lightgray);outline-offset:1px}.leaflet-container a{color:#0078a8}.leaflet-zoom-box{border:2px dotted #38f;background:#ffffff80}.leaflet-container{font-family:Helvetica Neue,Arial,Helvetica,sans-serif;font-size:12px;font-size:.75rem;line-height:1.5}.leaflet-bar{border-radius:4px}.leaflet-bar a,.leaflet-bar div{cursor:pointer;background-color:var(--light);border-bottom:1px solid var(--lightgray);border-radius:0;width:26px;height:26px;line-height:26px;display:block;text-align:center;text-decoration:none;color:var(--dark)}.leaflet-bar div svg{margin-top:3px}.leaflet-bar a,.leaflet-bar div,.leaflet-control-layers-toggle{background-position:50% 50%;background-repeat:no-repeat}.leaflet-bar a,.leaflet-control-layers-toggle{display:block}.leaflet-bar a:hover,.leaflet-bar a:focus,.leaflet-bar div:hover,.leaflet-bar div:focus{color:var(--tertiary);background-color:var(--lightgray)}.leaflet-bar a:first-child,.leaflet-bar div:first-child{border-top-left-radius:4px;border-top-right-radius:4px}.leaflet-bar a:last-child,.leaflet-bar div:last-child{border-bottom-left-radius:4px;border-bottom-right-radius:4px;border-bottom:none}.leaflet-bar a.leaflet-disabled,.leaflet-bar div.selected{cursor:default;background-color:var(--darkgray);color:var(--gray)}.leaflet-touch .leaflet-bar a,.leaflet-touch .leaflet-bar div{width:30px;height:30px;line-height:30px}.leaflet-touch .leaflet-bar a:first-child,.leaflet-touch .leaflet-bar div:first-child{border-radius:2px 2px 0 0/2px 2px 0px 0px}.leaflet-touch .leaflet-bar a:last-child,.leaflet-touch .leaflet-bar div:last-child{border-radius:0 0 2px 2px/0px 0px 2px 2px}.leaflet-control-zoom-in,.leaflet-control-zoom-out{font:700 18px Lucida Console,Monaco,monospace;text-indent:1px}.leaflet-touch .leaflet-control-zoom-in,.leaflet-touch .leaflet-control-zoom-out{font-size:22px}.leaflet-control-layers{box-shadow:0 1px 5px #0006;background:#fff;border-radius:5px}.leaflet-control-layers-toggle{background-image:url(data:image/svg+xml,%3Csvg%20xmlns%3D%27http://www.w3.org/2000/svg%27%20viewBox%3D%270%200%2024%2024%27%20fill%3D%27none%27%20stroke%3D%27%23333333%27%20stroke-width%3D%272%27%20stroke-linecap%3D%27round%27%20stroke-linejoin%3D%27round%27%3E%3Cpath%20d%3D%27M12.83%202.18a2%202%200%200%200-1.66%200L2.6%206.08a1%201%200%200%200%200%201.83l8.58%203.91a2%202%200%200%200%201.66%200l8.58-3.9a1%201%200%200%200%200-1.83Z%27/%3E%3Cpath%20d%3D%27m22%2017.65-9.17%204.16a2%202%200%200%201-1.66%200L2%2017.65%27/%3E%3Cpath%20d%3D%27m22%2012.65-9.17%204.16a2%202%200%200%201-1.66%200L2%2012.65%27/%3E%3C/svg%3E);background-size:22px 22px;width:36px;height:36px}.leaflet-retina .leaflet-control-layers-toggle{background-size:22px 22px}.leaflet-touch .leaflet-control-layers-toggle{width:44px;height:44px}.leaflet-control-layers .leaflet-control-layers-list,.leaflet-control-layers-expanded .leaflet-control-layers-toggle{display:none}.leaflet-control-layers-expanded .leaflet-control-layers-list{display:block;position:relative}.leaflet-control-layers-expanded{padding:6px 10px 6px 6px;color:#333;background:#fff}.leaflet-control-layers-scrollbar{overflow-y:scroll;overflow-x:hidden;padding-right:5px}.leaflet-control-layers-selector{margin-top:2px;position:relative;top:1px}.leaflet-control-layers label{display:block;font-size:13px;font-size:1.08333em}.leaflet-control-layers-separator{height:0;border-top:1px solid #ddd;margin:5px -10px 5px -6px}.leaflet-default-icon-path{background-image:url(images/marker-icon.png)}.leaflet-container .leaflet-control-attribution{background:#fff;background:#fffc;margin:0}.leaflet-control-attribution,.leaflet-control-scale-line{padding:0 5px;color:#333;line-height:1.4}.leaflet-control-attribution a{text-decoration:none}.leaflet-control-attribution a:hover,.leaflet-control-attribution a:focus{text-decoration:underline}.leaflet-attribution-flag{display:inline!important;vertical-align:baseline!important;width:1em;height:.6669em}.leaflet-left .leaflet-control-scale{margin-left:5px}.leaflet-bottom .leaflet-control-scale{margin-bottom:5px}.leaflet-control-scale-line{border:2px solid #777;border-top:none;line-height:1.1;padding:2px 5px 1px;white-space:nowrap;-moz-box-sizing:border-box;box-sizing:border-box;background:#fffc;text-shadow:1px 1px #fff}.leaflet-control-scale-line:not(:first-child){border-top:2px solid #777;border-bottom:none;margin-top:-2px}.leaflet-control-scale-line:not(:first-child):not(:last-child){border-bottom:2px solid #777}.leaflet-touch .leaflet-control-attribution,.leaflet-touch .leaflet-control-layers,.leaflet-touch .leaflet-bar{box-shadow:none}.leaflet-touch .leaflet-control-layers,.leaflet-touch .leaflet-bar{border:2px solid rgba(0,0,0,.2);background-clip:padding-box}.leaflet-popup{position:absolute;text-align:center;margin-bottom:20px}.leaflet-popup-content-wrapper{padding:1px;text-align:left;border-radius:12px}.leaflet-popup-content{margin:13px 24px 13px 20px;line-height:1.3;font-size:13px;font-size:1.08333em;min-height:1px}.leaflet-popup-content p{margin:1.3em 0}.leaflet-popup-tip-container{width:40px;height:20px;position:absolute;left:50%;margin-top:-1px;margin-left:-20px;overflow:hidden;pointer-events:none}.leaflet-popup-tip{width:17px;height:17px;padding:1px;margin:-10px auto 0;pointer-events:auto;-webkit-transform:rotate(45deg);-moz-transform:rotate(45deg);-ms-transform:rotate(45deg);transform:rotate(45deg)}.leaflet-popup-content-wrapper,.leaflet-popup-tip{background:#fff;color:#333;box-shadow:0 3px 14px #0006}.leaflet-container a.leaflet-popup-close-button{position:absolute;top:0;right:0;border:none;text-align:center;width:24px;height:24px;font:16px/24px Tahoma,Verdana,sans-serif;color:#757575;text-decoration:none;background:transparent}.leaflet-container a.leaflet-popup-close-button:hover,.leaflet-container a.leaflet-popup-close-button:focus{color:#585858}.leaflet-popup-scrolled{overflow:auto}.leaflet-oldie .leaflet-popup-content-wrapper{-ms-zoom:1;zoom:1}.leaflet-oldie .leaflet-popup-tip{width:24px;margin:0 auto;-ms-filter:"progid:DXImageTransform.Microsoft.Matrix(M11=0.70710678, M12=0.70710678, M21=-0.70710678, M22=0.70710678)";filter:progid:DXImageTransform.Microsoft.Matrix(M11=.70710678,M12=.70710678,M21=-.70710678,M22=.70710678)}.leaflet-oldie .leaflet-control-zoom,.leaflet-oldie .leaflet-control-layers,.leaflet-oldie .leaflet-popup-content-wrapper,.leaflet-oldie .leaflet-popup-tip{border:1px solid #999}.leaflet-div-icon{background:#fff;border:1px solid #666}.leaflet-tooltip{position:absolute;padding:6px;background-color:#fff;border:1px solid #fff;border-radius:3px;color:#222;white-space:nowrap;-webkit-user-select:none;-moz-user-select:none;-ms-user-select:none;user-select:none;pointer-events:none;box-shadow:0 1px 3px #0006}.leaflet-tooltip.leaflet-interactive{cursor:pointer;pointer-events:auto}.leaflet-tooltip-top:before,.leaflet-tooltip-bottom:before,.leaflet-tooltip-left:before,.leaflet-tooltip-right:before{position:absolute;pointer-events:none;border:6px solid transparent;background:transparent;content:""}.leaflet-tooltip-bottom{margin-top:6px}.leaflet-tooltip-top{margin-top:-6px}.leaflet-tooltip-bottom:before,.leaflet-tooltip-top:before{left:50%;margin-left:-6px}.leaflet-tooltip-top:before{bottom:0;margin-bottom:-12px;border-top-color:#fff}.leaflet-tooltip-bottom:before{top:0;margin-top:-12px;margin-left:-6px;border-bottom-color:#fff}.leaflet-tooltip-left{margin-left:-6px}.leaflet-tooltip-right{margin-left:6px}.leaflet-tooltip-left:before,.leaflet-tooltip-right:before{top:50%;margin-top:-6px}.leaflet-tooltip-left:before{right:0;margin-right:-12px;border-left-color:#fff}.leaflet-tooltip-right:before{left:0;margin-left:-12px;border-right-color:#fff}@media print{.leaflet-control{-webkit-print-color-adjust:exact;print-color-adjust:exact}}`,
        },
      ],
      js: [
        {
          loadTime: "afterDOMReady",
          src: `https://unpkg.com/leaflet@${C.versions.leaflet}`,
          contentType: "external",
        },
        {
          loadTime: "beforeDOMReady",
          src: `https://unpkg.com/lucide@${C.versions.lucide}`,
          contentType: "external",
        },
        {
          loadTime: "afterDOMReady",
          contentType: "inline",
          script: `var __extends=this&&this.__extends||function(){var e=function(n,t){return e=Object.setPrototypeOf||{__proto__:[]}instanceof Array&&function(o,i){o.__proto__=i}||function(o,i){for(var r in i)Object.prototype.hasOwnProperty.call(i,r)&&(o[r]=i[r])},e(n,t)};return function(n,t){if(typeof t!="function"&&t!==null)throw new TypeError("Class extends value "+String(t)+" is not a constructor or null");e(n,t);function o(){this.constructor=n}n.prototype=t===null?Object.create(t):(o.prototype=t.prototype,new o)}}(),__assign=this&&this.__assign||function(){return __assign=Object.assign||function(e){for(var n,t=1,o=arguments.length;t<o;t++){n=arguments[t];for(var i in n)Object.prototype.hasOwnProperty.call(n,i)&&(e[i]=n[i])}return e},__assign.apply(this,arguments)},__awaiter=this&&this.__awaiter||function(e,n,t,o){function i(r){return r instanceof t?r:new t(function(l){l(r)})}return new(t||(t=Promise))(function(r,l){function s(c){try{a(o.next(c))}catch(d){l(d)}}function u(c){try{a(o.throw(c))}catch(d){l(d)}}function a(c){c.done?r(c.value):i(c.value).then(s,u)}a((o=o.apply(e,n||[])).next())})},__generator=this&&this.__generator||function(e,n){var t={label:0,sent:function(){if(r[0]&1)throw r[1];return r[1]},trys:[],ops:[]},o,i,r,l=Object.create((typeof Iterator=="function"?Iterator:Object).prototype);return l.next=s(0),l.throw=s(1),l.return=s(2),typeof Symbol=="function"&&(l[Symbol.iterator]=function(){return this}),l;function s(a){return function(c){return u([a,c])}}function u(a){if(o)throw new TypeError("Generator is already executing.");for(;l&&(l=0,a[0]&&(t=0)),t;)try{if(o=1,i&&(r=a[0]&2?i.return:a[0]?i.throw||((r=i.return)&&r.call(i),0):i.next)&&!(r=r.call(i,a[1])).done)return r;switch(i=0,r&&(a=[a[0]&2,r.value]),a[0]){case 0:case 1:r=a;break;case 4:return t.label++,{value:a[1],done:!1};case 5:t.label++,i=a[1],a=[0];continue;case 7:a=t.ops.pop(),t.trys.pop();continue;default:if(r=t.trys,!(r=r.length>0&&r[r.length-1])&&(a[0]===6||a[0]===2)){t=0;continue}if(a[0]===3&&(!r||a[1]>r[0]&&a[1]<r[3])){t.label=a[1];break}if(a[0]===6&&t.label<r[1]){t.label=r[1],r=a;break}if(r&&t.label<r[2]){t.label=r[2],t.ops.push(a);break}r[2]&&t.ops.pop(),t.trys.pop();continue}a=n.call(e,t)}catch(c){a=[6,c],i=0}finally{o=r=0}if(a[0]&5)throw a[1];return{value:a[0]?a[1]:void 0,done:!0}}},C={map:{default:{minZoom:"0",maxZoom:"2",zoomDelta:"0.5",zoomSnap:"0.01",height:"600",scale:"1",unit:"",enableCopyTool:"false"}}},MARKER_CATEGORY_LABELS={settlement:"Settlements","holy-site":"Holy sites",landmark:"Landmarks",nation:"Nations"};function isNonEmptyObject(e){return!e||typeof e!="object"||Array.isArray(e)?!1:Object.keys(e).length>0&&Object.values(e).every(function(n){return typeof n=="string"})}function parseCoordinates(e){var n=e.replace(/\s/g,"").split(",").map(function(t){return parseInt(t)});if(!isLatLngTuple(n))throw new Error("Coordinates not properly validated");return n}function isLatLngTuple(e){return!!e&&Array.isArray(e)&&e.length===2&&e.every(function(n){return typeof n=="number"&&!isNaN(n)})}function createIcons(e){lucide.createIcons({attrs:{class:["leaflet-marker-inner-icon"]},root:e})}function distance(e,n){var t=function(o){return o*o};return Math.sqrt(t(e.lat-n.lat)+t(e.lng-n.lng))}function getIcon(e){var n=document.createElement("i");return n.setAttribute("data-lucide",e),lucide.createIcons({root:n}),n}function isMarkerDataSet(e){return!(!isNonEmptyObject(e)||!e.name||!e.link||!e.coordinates||!e.icon||!e.colour||!e.minZoom)}function getMarkerData(e){var n=e.querySelectorAll("div.leaflet-marker"),t=[];return n.forEach(function(o){isMarkerDataSet(o.dataset)&&t.push(o.dataset),o.remove()}),t}function buildMarkerIcon(e,n,t,s){var w='<svg class="leaflet-marker-pin" style="fill:'.concat(t,'" viewBox="0 0 32 48"><path d="m32,19c0,12 -12,24 -16,29c-4,-5 -16,-16 -16,-29a16,19 0 0 1 32,0"/></svg><i data-lucide="').concat(n,'"></i>');return L.divIcon({className:"leaflet-marker-icon",html:s?w:'<a href="'.concat(e,'">').concat(w,"</a>"),iconSize:[32,48],iconAnchor:[16,48],tooltipAnchor:[17,-30],popupAnchor:[0,-44]})}var addMarker=function(e,n,g){var t=function(h,f,v){var m=1e-5;f.getZoom()>=v-m?h.addTo(g):g.removeLayer(h);var p=h.getElement();p&&createIcons(p)},o=e.link,i=e.icon,r=e.colour,l=e.minZoom,s=e.coordinates,u=e.name,a={icon:buildMarkerIcon(o,i,r,!1)},c=parseFloat(l),d=L.marker(parseCoordinates(s),a).bindTooltip(u);t(d,n,c),n.on("zoomend",function(){return t(d,n,c)})},addMarkersByCategory=function(e,n){var d=L.layerGroup().addTo(n),g={},o={};e.forEach(function(u){var k=u.category&&MARKER_CATEGORY_LABELS[u.category]?u.category:"";if(k===""){addMarker(u,n,d);return}g[k]||(g[k]=L.layerGroup().addTo(n)),addMarker(u,n,g[k])}),Object.keys(MARKER_CATEGORY_LABELS).forEach(function(k){g[k]&&(o[MARKER_CATEGORY_LABELS[k]]=g[k])}),Object.keys(o).length>0&&L.control.layers(null,o).addTo(n),n.on("overlayadd",function(){createIcons(n.getContainer())})};var SubControl=function(){function e(n){this.onSelectCallback=function(){},this.options=__assign(__assign({},C.map.default),{defaultZoom:C.map.default.minZoom,src:""}),this._isSelected=!1,this.index=n.index,this.map=n.map,this.onSelectCallback=n.onSelectCallback}return Object.defineProperty(e.prototype,"isSelected",{get:function(){return this._isSelected},enumerable:!1,configurable:!0}),e.prototype.setSelected=function(n){var t,o;this._isSelected!==n&&(this._isSelected=n,n?((t=this.button)===null||t===void 0||t.classList.add("selected"),this.onSelected()):((o=this.button)===null||o===void 0||o.classList.remove("selected"),this.onDeselected()))},e.prototype.onAdd=function(n){var t=this;this.button=L.DomUtil.create("div","leaflet-control-button",n),this.button.addEventListener("click",function(){return t.onSelectCallback(t.index)}),L.DomEvent.disableClickPropagation(n),this.onAdded()},e.prototype.onRemove=function(){var n,t;this.onRemoved(),(n=this.button)===null||n===void 0||n.removeEventListener("click",function(){}),(t=this.button)===null||t===void 0||t.replaceChildren()},e.prototype.updateSettings=function(n){this.options=__assign(__assign({},this.options),n)},e.prototype.onAdded=function(){throw new Error("Not implemented")},e.prototype.onRemoved=function(){},e.prototype.onSelected=function(){},e.prototype.onDeselected=function(){},e.prototype.mapClicked=function(n){throw new Error("Not implemented")},e}(),PanControl=function(e){__extends(n,e);function n(){return e!==null&&e.apply(this,arguments)||this}return n.prototype.onAdded=function(){this.button&&(this.button.appendChild(lucide.createElement(lucide.MousePointer2)),this.button.ariaLabel="Pan")},n.prototype.mapClicked=function(t){},n}(SubControl),MeasureState;(function(e){e[e.Ready=0]="Ready",e[e.Measuring=1]="Measuring",e[e.Finishing=2]="Finishing",e[e.Done=3]="Done"})(MeasureState||(MeasureState={}));var MeasureControl=function(e){__extends(n,e);function n(){var t=e!==null&&e.apply(this,arguments)||this;return t.state=MeasureState.Ready,t.pathItems=[],t.distance=0,t}return n.prototype.onAdded=function(){this.button&&(this.button.appendChild(lucide.createElement(lucide.Ruler)),this.button.ariaLabel="Measure"),this.lineLayer=L.layerGroup().addTo(this.map),this.pointLayer=L.layerGroup().addTo(this.map),this.pathLine=L.polyline([]).addTo(this.lineLayer),this.previewLine=L.polyline([],{dashArray:"8"}).addTo(this.lineLayer),this.previewTooltip=this.getTooltip(!0).setLatLng([0,0])},n.prototype.onSelected=function(){var t=this;this.map.getContainer().style.cursor="crosshair",this.map.on("mousemove",function(o){t.renderPreview(o.latlng)})},n.prototype.onDeselected=function(){this.map.getContainer().style.cursor="",this.map.removeEventListener("mousemove"),this.resetPath(),this.state=MeasureState.Ready},n.prototype.mapClicked=function(t){var o,i,r;if(!this.lineLayer)throw new Error("Line layer not initialised");switch(this.state){case MeasureState.Ready:case MeasureState.Measuring:{this.state=MeasureState.Measuring,this.pathItems.push(t.latlng),this.renderPath(),(o=this.previewTooltip)===null||o===void 0||o.addTo(this.lineLayer),this.renderPreview(t.latlng);break}case MeasureState.Finishing:{this.state=MeasureState.Done,(i=this.lastElement)===null||i===void 0||i.bindTooltip(this.getTooltip(!0)).bringToFront(),(r=this.previewTooltip)===null||r===void 0||r.remove();break}case MeasureState.Done:this.resetPath(),this.state=MeasureState.Ready}},n.prototype.renderPath=function(){this.cleanLastElement(),this.updatePolyline(this.pathLine,this.pathItems);var t=this.pathItems.at(-1);if(t!==void 0){this.lastElement=this.getCircleMarker(t);var o=this.pathItems.at(-2);o!==void 0&&(this.distance+=distance(t,o)*parseFloat(this.options.scale))}},n.prototype.renderPreview=function(t){var o;if(this.state===MeasureState.Measuring){var i=this.pathItems.at(-1);i!==void 0&&(this.updatePolyline(this.previewLine,[i,t]),this.previewTooltip=(o=this.previewTooltip)===null||o===void 0?void 0:o.setLatLng(t).setContent(this.getContent(this.distance+distance(i,t)*parseFloat(this.options.scale))))}},n.prototype.resetPath=function(){var t,o;this.pathItems=[],this.distance=0,this.cleanLastElement(),(t=this.pointLayer)===null||t===void 0||t.clearLayers(),this.updatePolyline(this.pathLine,[]),this.updatePolyline(this.previewLine,[]),(o=this.previewTooltip)===null||o===void 0||o.remove()},n.prototype.updatePolyline=function(t,o){var i;t?.setLatLngs(o).redraw(),(i=t?.getElement())===null||i===void 0||i.classList.remove("leaflet-interactive")},n.prototype.cleanLastElement=function(){var t,o,i;(t=this.lastElement)===null||t===void 0||t.removeEventListener("click"),(i=(o=this.lastElement)===null||o===void 0?void 0:o.getElement())===null||i===void 0||i.classList.remove("leaflet-interactive")},n.prototype.getTooltip=function(t){return t===void 0&&(t=!1),L.tooltip({permanent:t,offset:[15,0]}).setContent(this.getContent(this.distance))},n.prototype.getCircleMarker=function(t){var o=this;if(!this.pointLayer)throw new Error("Point layer not initialised");return L.circleMarker(t,{radius:4,fill:!0,fillColor:"#3388ff",fillOpacity:1}).addTo(this.pointLayer).addEventListener("click",function(){return o.state=MeasureState.Finishing})},n.prototype.getContent=function(t){var o,i;return"".concat(t.toFixed(1)," ").concat((i=(o=this.options)===null||o===void 0?void 0:o.unit)!==null&&i!==void 0?i:C.map.default.unit)},n}(SubControl),CopyControl=function(e){__extends(n,e);function n(){return e!==null&&e.apply(this,arguments)||this}return n.prototype.onAdded=function(){this.button&&(this.button.appendChild(lucide.createElement(lucide.Pin)),this.button.ariaLabel="Copy"),this.previewTooltip=L.tooltip({permanent:!0,offset:[15,0]}).setLatLng([0,0])},n.prototype.onSelected=function(){var t=this,o;this.map.getContainer().style.cursor="crosshair",this.map.on("mousemove",function(i){t.renderPreview(i.latlng)}),(o=this.previewTooltip)===null||o===void 0||o.addTo(this.map)},n.prototype.onDeselected=function(){var t;this.map.getContainer().style.cursor="",this.map.removeEventListener("mousemove"),(t=this.previewTooltip)===null||t===void 0||t.remove()},n.prototype.mapClicked=function(t){navigator.clipboard.writeText(this.getContent(t.latlng))},n.prototype.renderPreview=function(t){var o;(o=this.previewTooltip)===null||o===void 0||o.setContent(this.getContent(t)).setLatLng(t)},n.prototype.getContent=function(t){return"".concat(Math.round(t.lat),", ").concat(Math.round(t.lng))},n}(SubControl),DefaultControlContainerOptions={enableCopyTool:!1},ControlContainer=function(e){__extends(n,e);function n(t){var o=e.call(this,{position:"topleft"})||this;return o.controls=[],o.activeIndex=0,o.settings=__assign(__assign({},DefaultControlContainerOptions),t),o}return n.prototype.onAdd=function(t){var o=this,i;this.registerSubControl(PanControl,t),this.registerSubControl(MeasureControl,t),this.settings.enableCopyTool&&this.registerSubControl(CopyControl,t);var r=L.DomUtil.create("div","leaflet-bar leaflet-control");return this.controls.forEach(function(l){return l.onAdd(r)}),(i=this.controls[this.activeIndex])===null||i===void 0||i.setSelected(!0),t.on("click",function(l){return o.controls.forEach(function(s){s.isSelected&&s.mapClicked(l)})}),r},n.prototype.onRemove=function(t){t?.removeEventListener("click"),this.controls.forEach(function(o){return o.onRemove()}),this.controls=[]},n.prototype.updateSettings=function(t){this.controls.forEach(function(o){return o.updateSettings(t)})},n.prototype.registerSubControl=function(t,o){var i=this,r=function(s){var u,a;(u=i.controls.at(i.activeIndex))===null||u===void 0||u.setSelected(!1),(a=i.controls.at(s))===null||a===void 0||a.setSelected(!0),i.activeIndex=s},l={index:this.controls.length,map:o,onSelectCallback:r};this.controls.push(new t(l))},n}(L.Control);function isMapDataSet(e){return!(!isNonEmptyObject(e)||!e.src||!e.height||!e.minZoom||!e.maxZoom||!e.defaultZoom||!e.zoomDelta||!e.scale||e.unit===void 0)}function getImageMeta(e){return __awaiter(this,void 0,Promise,function(){return __generator(this,function(n){return[2,new Promise(function(t,o){var i=new Image;i.onload=function(){return t(i)},i.onerror=function(r){return o(r)},i.src=e})]})})}function initialiseMap(e,n){return __awaiter(this,void 0,Promise,function(){var t,o,i,r,l;return __generator(this,function(s){switch(s.label){case 0:return t=e.dataset,isMapDataSet(t)?[4,getImageMeta(t.src)]:[2];case 1:return o=s.sent(),e.style.aspectRatio=(o.naturalWidth/o.naturalHeight).toString(),i=[[0,0],[o.naturalHeight,o.naturalWidth]],r=L.map(e,{crs:L.CRS.Simple,maxBounds:i,minZoom:parseFloat(t.minZoom),maxZoom:parseFloat(t.maxZoom),zoomSnap:.01,zoomDelta:parseFloat(t.zoomDelta)}),l=new ControlContainer({enableCopyTool:t.enableCopyTool==="true"}),l.addTo(r),l.updateSettings(t),t.caption&&(r.attributionControl.setPrefix(!1),r.attributionControl.addAttribution(t.caption)),L.imageOverlay(t.src,i).addTo(r),r.fitBounds(i),addMarkersByCategory(n,r),r.setZoom(parseFloat(t.defaultZoom)),[2,r]}})})}function cleanupMap(e){e?.clearAllEventListeners(),e?.remove()}document.addEventListener("nav",function(){return __awaiter(void 0,void 0,void 0,function(){var e;return __generator(this,function(n){return e=document.querySelectorAll("div.leaflet-map"),e.forEach(function(t){return __awaiter(void 0,void 0,void 0,function(){var o,i;return __generator(this,function(r){switch(r.label){case 0:return o=getMarkerData(t),[4,initialiseMap(t,o)];case 1:return i=r.sent(),window.addCleanup(function(){return cleanupMap(i)}),[2]}})})}),[2]})})});`,
        },
      ],
    }
  },
})
