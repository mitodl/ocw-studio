import { last, trim } from "lodash"

import { Shortcode, ShortcodeParam } from "./util"
import { Website, WebsiteContent } from "../../../types/websites"

/**
 * Helpers for the params on `image-gallery` and `image-gallery-item`
 * shortcodes.
 *
 * The same Markdown is built by two themes, which read different params:
 * course-v2 shows the file named by an item's `href`, joined onto the gallery's
 * `baseUrl`, captioned with the item's `text`; course-v3 finds the image
 * resource by the item's `uuid`. Existing galleries carry other params too
 * (`id`, `data-ngdesc`). The editor keeps each tag's raw param text exactly as
 * authored, so these helpers only read from it, or build it for new items.
 */

export interface GalleryItemParams {
  uuid?: string
  href?: string
  text?: string
}

/**
 * Read the params Studio uses out of an item's raw param text, i.e.
 * everything between `image-gallery-item` and `>}}`.
 *
 * Only for display and for spotting duplicates: the raw text is what gets
 * saved. Params that do not parse (an unpaired quote, say) yield nothing
 * rather than an error, and the item still round-trips untouched.
 */
export const parseGalleryItem = (raw: string): GalleryItemParams => {
  try {
    const shortcode = Shortcode.fromString(
      `{{< image-gallery-item ${raw.trim()} >}}`,
    )
    return {
      uuid: shortcode.get("uuid"),
      href: shortcode.get("href"),
      text: shortcode.get("text"),
    }
  } catch {
    return {}
  }
}

const fileBasename = (file: string): string => {
  // A base URL is needed only to parse a relative path; it never ends up in
  // the result.
  const basename = last(
    new URL(file, "https://ocw.invalid").pathname.split("/"),
  )
  try {
    return decodeURIComponent(basename ?? "")
  } catch {
    return basename ?? ""
  }
}

/**
 * The image's caption, with Windows line endings made plain newlines. Some
 * captions are stored with "\r\n", and ShortcodeParam only flattens "\n".
 */
const imageCaption = (resource: WebsiteContent): string => {
  const imageMetadata = resource.metadata?.image_metadata
  const caption =
    imageMetadata && typeof imageMetadata === "object"
      ? (imageMetadata as Record<string, unknown>).caption
      : undefined
  return typeof caption === "string" ? caption.replace(/\r\n?/g, "\n") : ""
}

/**
 * The raw param text for a newly added item.
 *
 * `uuid` is for course-v3. `href` and `text` are for course-v2: the file's
 * basename, which is the form the gallery_image_rename cleanup rule keeps hrefs
 * in, and the image's caption. `text` is written even when empty, as every
 * existing item has one.
 *
 * `text` has to fit on one line, so each line break in the caption becomes a
 * space (a paragraph break, two) and double quotes are escaped. Items written
 * from captions in production follow the same convention.
 */
export const buildGalleryItem = (resource: WebsiteContent): string => {
  const params = [
    new ShortcodeParam(resource.text_id, "uuid"),
    ...(resource.file
      ? [new ShortcodeParam(fileBasename(resource.file), "href")]
      : []),
    new ShortcodeParam(imageCaption(resource), "text"),
  ]
  return ` ${params.map((param) => param.toHugo()).join(" ")} `
}

/**
 * The `baseUrl` a new gallery needs for course-v2, which joins each item's
 * bare-filename `href` onto it: the site's URL path, as on every existing
 * gallery, e.g. "/courses/18-05-introduction-to-probability-spring-2014/".
 *
 * A site that has never been published may not have a URL path yet, so fall
 * back to the one Studio would suggest. The author can still change the URL
 * before the first publish, which would leave this stale. A suggestion that
 * still contains unfilled "[sitemetadata:...]" sections is unusable, and there
 * is then no baseUrl to give.
 */
export const galleryBaseUrl = (website: Website): string | null => {
  let urlPath = website.url_path
  if (!urlPath) {
    const suggestion = website.url_suggestion
    if (!suggestion || /[[\]]/.test(suggestion)) {
      return null
    }
    urlPath = [website.starter?.config?.["root-url-path"], suggestion]
      .filter(Boolean)
      .join("/")
  }
  return `/${trim(urlPath, "/")}/`
}
