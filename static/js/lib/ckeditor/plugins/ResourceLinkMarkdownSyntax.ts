import Turndown from "turndown"
import Showdown from "showdown"
import { Editor } from "@ckeditor/ckeditor5-core"
import invariant from "tiny-invariant"

import MarkdownSyntaxPlugin from "./MarkdownSyntaxPlugin"
import { TurndownRule } from "../../../types/ckeditor_markdown"

import { Shortcode, escapeShortcodes } from "./util"
import { turndownService } from "../turndown"
import { RESOURCE_LINK_CONFIG_KEY } from "./constants"

const RESOURCE_LINK_SHORTCODE_REGEX = Shortcode.regex("resource_link", true)

const queryKeys = {
  uuid: "ocw_resource_link_uuid",
  suffix: "ocw_resource_link_suffix",
}

/**
 * Class for defining Markdown conversion rules for Resource links.
 *  - Converts from markdown to HTML when populating CKEditor
 *  - Converts from HTML to markdown when saving
 *
 * Resource links are stored in markdown as:
 *
 * ```md
 * {{% resource_link "some-uuid" "Title of Link" "optional-link-suffix" %}}
 * ```
 *
 * and in HTML as:
 * ```html
 * <a href="{previewURL} \
 *  ?ocw_resource_link_uuid={some-uuid} \
 *  &ocw_resource_link_suffix={optional-link-suffix}"
 * > Title of Link </a>
 * ```
 * Where:
 *  - {previewURL} portion is ONLY used for previewing the resource in CKEditor
 *    and is generated by a template specified in CKEditor's `resource-link`
 *    configuration item.
 *
 */
export default class ResourceLinkMarkdownSyntax extends MarkdownSyntaxPlugin {
  hrefTemplate: string

  static get pluginName(): string {
    return "ResourceLinkMarkdownSyntax"
  }

  constructor(editor: Editor) {
    super(editor)
    this.hrefTemplate = editor.config.get(RESOURCE_LINK_CONFIG_KEY).hrefTemplate
    this.validateConfig()
  }

  private validateConfig() {
    invariant(this.hrefTemplate !== undefined, "hrefTemplate is undefined")
    try {
      this.makeResourceLinkHref("fake-uuid", "fake-fragment")
    } catch (err) {
      console.error("The hrefTemplate is invalid:")
      throw err
    }
  }

  isResourceLinkHref = (href?: string): boolean => {
    if (!href) return false
    try {
      const url = new URL(href)
      return url.searchParams.has(queryKeys.uuid)
    } catch (err) {
      /**
       * Invalid URLs like "mit.edu" are allowed but are not resource link URLs
       */
      return false
    }
  }

  getResourceLinkID = (href?: string): string | null => {
    if (this.isResourceLinkHref(href)) {
      const url = new URL(href)
      return url.searchParams.get(queryKeys.uuid)
    } else {
      return ""
    }
  }

  makeResourceLinkHref = (uuid: string, suffix = "") => {
    const href = new URL(this.hrefTemplate.replace(/:uuid/g, uuid))
    href.searchParams.set(queryKeys.uuid, uuid)
    href.searchParams.set(queryKeys.suffix, suffix)
    return href.toString()
  }

  /**
   * Strip resource-link-specific query params from a URL. (Those query params
   * are an implementation detail ahd should not be visible in UI.)
   */
  makePreviewHref = (href: string): string => {
    const url = new URL(href)
    url.searchParams.delete(queryKeys.uuid)
    url.searchParams.delete(queryKeys.suffix)
    return url.toString()
  }

  get showdownExtension() {
    return (): Showdown.ShowdownExtension[] => {
      return [
        {
          type: "lang",
          regex: RESOURCE_LINK_SHORTCODE_REGEX,
          replace: (s: string) => {
            const shortcode = Shortcode.fromString(s)
            const uuid = shortcode.get(0)
            if (!uuid) {
              throw new Error("resource_link shortcode must have a uuid")
            }
            const text = escapeShortcodes(shortcode.get(1) ?? "")
            const suffix = shortcode.get(2) ?? ""
            const href = this.makeResourceLinkHref(uuid, suffix)
            return `<a href="${href}">${text}</a>`
          },
        },
      ]
    }
  }

  get turndownRules(): TurndownRule[] {
    return [
      {
        name: `${ResourceLinkMarkdownSyntax.pluginName}-turndown`,
        rule: {
          filter: (node) => {
            if (node.nodeName !== "A") return false
            const anchor = node as HTMLAnchorElement
            return this.isResourceLinkHref(anchor.href)
          },
          replacement: (_content: string, node: Turndown.Node): string => {
            const anchor = node as HTMLAnchorElement
            const url = new URL(anchor.href)
            const search = new URLSearchParams(url.search)
            const uuid = search.get(queryKeys.uuid)
            const suffix = search.get(queryKeys.suffix) ?? ""
            if (!uuid) {
              throw new Error(`${queryKeys.suffix} not found in URL`)
            }

            const text = turndownService
              .turndown(anchor.innerHTML)
              /**
               * When turndown converts innerHTML to markdown, it will convert
               * `{{&lt;` to `{{\<`. So we need to unescape that.
               */
              .replace(/{{\\</g, "{{<")

            return Shortcode.resourceLink(uuid, text, suffix).toHugo()
          },
        },
      },
    ]
  }
}
