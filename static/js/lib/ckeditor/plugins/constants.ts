export const ADD_RESOURCE_LINK = "addResourceLink"

export const ADD_RESOURCE_EMBED = "addResourceEmbed"

export const MINIMAL_WITH_MATH = "with-math" as const

export const CKEDITOR_RESOURCE_UTILS = "CKEDITOR_RESOURCE_UTILS"

export const RESOURCE_EMBED = "resourceEmbed"

export const RESOURCE_LINK = "resourceLink"

export const RESOURCE_EMBED_COMMAND = "insertResourceEmbed"

export const IMAGE_GALLERY = "imageGallery"

export const IMAGE_GALLERY_COMMAND = "insertImageGallery"

export const ADD_IMAGE_GALLERY = "addImageGallery"

export const MARKDOWN_CONFIG_KEY = "markdown-config"

export const RESOURCE_LINK_CONFIG_KEY = "resource-link-config"

export const WEBSITE_NAME = "website-name"

import TurndownService from "turndown"

/**
 * Union type capturing the possible typs of resource nodes we
 * support in CKEditor
 *
 * CKEResourceNodeType
 */
export type CKEResourceNodeType = typeof RESOURCE_LINK | typeof RESOURCE_EMBED

/**
 * A 'resource renderer'
 *
 * A function of this type is passed down from the React component
 * that wraps CKEditor to the CKEditor config. It can then be called
 * in the `editingDowncast` handler function on the plugins for
 * resource links and embeds.
 */
export interface RenderResourceFunc {
  (uuid: string, el: HTMLElement): void
}

/**
 * A handle passed to the React layer for a single image gallery widget.
 *
 * The gallery widget needs to *write* to the CKEditor model, not just read
 * from it like `RenderResourceFunc` does. These callbacks are built in the
 * editingDowncast converter, where the model element for this particular
 * gallery is in scope, so React never has to know about CKEditor internals.
 */
export interface ImageGalleryHandle {
  getUuids(): string[]
  setUuids(uuids: string[]): void
  /** Subscribe to model changes. Returns an unsubscribe function. */
  onModelChange(cb: () => void): () => void
  /** Open the resource picker to append more images to this gallery. */
  openPicker(): void
}

/**
 * A 'gallery renderer', analogous to RenderResourceFunc.
 *
 * Passed from the React component wrapping CKEditor into the editor config,
 * then called in the editingDowncast handler for image galleries.
 */
export interface RenderGalleryFunc {
  (el: HTMLElement, handle: ImageGalleryHandle): void
}

export type ResourceDialogMode = typeof RESOURCE_LINK | typeof RESOURCE_EMBED

export const TABLE_ELS: TurndownService.TagName[] = [
  "table",
  "tbody",
  "th",
  "td",
  "tr",
  "thead",
  "tfoot",
]

export const CONTENT_TABLE_ELS = ["th", "td"]

// A whitelist of attributes that can be assigned to table cells
export const TABLE_ALLOWED_ATTRS: string[] = ["colspan", "rowspan"]

/**
 * A regex designed to extract attributes from html tags or shortcodes
 *
 * It starts with matching 1 or more of anything but whitespace, then
 * an equals sign followed by a single or double quote. The regex ends
 * with a double quote and captures anything in between the quotes.
 */
export const ATTRIBUTE_REGEX =
  /(\S+)=["']?((?:.(?!["']?\s+(?:\S+)=|\s*\/?[>"']))+.)["']?/g

export const LEGACY_SHORTCODES = [
  "quiz_choice",
  "quiz_choices",
  "quiz_multiple_choice",
  "quiz_solution",
  "resource_file",
  "video-gallery",
  "youtube",
  "anchor",
  "approx-students",
  "br",
  "div-with-class",
  "fullwidth-cell",
  "h",
  "quote",
  "simplecast",
  "sub",
  "sup",
  "baseurl",
]
