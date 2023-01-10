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

/**
 * Class for defining Markdown conversion rules for Resource links
 *
 * These are stored in Markdown like this:
 *
 * ```md
 * {{% resource_link AUUIDUNLIKEANYOTHER "Here's a link to my resource" %}}
 * ```
 *
 * The first argument is the uuid of the resource to which we're linking, and
 * the second argument is that text that should be rendered inside of the link.
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
    return href.includes("?ocw_resource_link_uuid=")
  }

  makeResourceLinkHref = (uuid: string, fragment = "") => {
    const href = new URL(this.hrefTemplate.replace(/:uuid/g, uuid))
    href.searchParams.set("ocw_resource_link_uuid", uuid)
    href.searchParams.set("ocw_resource_link_fragment", fragment)
    return href.toString()
  }

  removeResourceLinkQueryParams = (href: string): string => {
    const url = new URL(href)
    url.searchParams.delete("ocw_resource_link_uuid")
    url.searchParams.delete("ocw_resource_link_fragment")
    return url.toString()
  }

  get showdownExtension() {
    return (): Showdown.ShowdownExtension[] => {
      return [
        {
          type:    "lang",
          regex:   RESOURCE_LINK_SHORTCODE_REGEX,
          replace: (s: string) => {
            const shortcode = Shortcode.fromString(s)
            const uuid = shortcode.get(0)
            if (!uuid) {
              throw new Error("resource_link shortcode must have a uuid")
            }
            const text = escapeShortcodes(shortcode.get(1) ?? "")
            const fragment = shortcode.get(2) ?? ""
            const href = this.makeResourceLinkHref(uuid, fragment)
            return `<a href="${href}">${text}</a>`
          }
        }
      ]
    }
  }

  get turndownRules(): TurndownRule[] {
    return [
      {
        name: `${ResourceLinkMarkdownSyntax.pluginName}-turndown`,
        rule: {
          filter: node => {
            if (node.nodeName !== "A") return false
            const anchor = node as HTMLAnchorElement
            return this.isResourceLinkHref(anchor.href)
          },
          replacement: (_content: string, node: Turndown.Node): string => {
            const anchor = node as HTMLAnchorElement
            const url = new URL(anchor.href)
            const search = new URLSearchParams(url.search)
            const uuid = search.get("ocw_resource_link_uuid")
            const hash = search.get("ocw_resource_link_fragment") ?? ""
            if (!uuid) {
              throw new Error("ocw_resource_link_uuid not found in URL")
            }

            const text = turndownService
              .turndown(anchor.innerHTML)
              /**
               * When turndown converts innerHTML to markdown, it will convert
               * `{{&lt;` to `{{\<`. So we need to unescape that.
               */
              .replace(/{{\\</g, "{{<")

            return Shortcode.resourceLink(uuid, text, hash).toHugo()
          }
        }
      }
    ]
  }
}
