import Turndown from "turndown"
import Showdown from "showdown"
import { editor } from "@ckeditor/ckeditor5-core"

import MarkdownSyntaxPlugin from "./MarkdownSyntaxPlugin"
import { TurndownRule } from "../../../types/ckeditor_markdown"

import {
  RESOURCE_LINK_CKEDITOR_CLASS,
  RESOURCE_LINK
} from "@mitodl/ckeditor5-resource-link/src/constants"
import { Shortcode, escapeShortcodes } from "./util"

export const encodeShortcodeArgs = (...args: (string | undefined)[]) =>
  encodeURIComponent(JSON.stringify(args))

const decodeShortcodeArgs = (encoded: string) =>
  JSON.parse(decodeURIComponent(encoded))

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
 * The ResourceEmbed plugin itself is provided via our fork of CKEditor's
 * 'link' plugin.
 */
export default class ResourceLinkMarkdownSyntax extends MarkdownSyntaxPlugin {
  constructor(editor: editor.Editor) {
    super(editor)
  }

  static get pluginName(): string {
    return "ResourceLinkMarkdownSyntax"
  }

  get showdownExtension() {
    return function resourceExtension(): Showdown.ShowdownExtension[] {
      return [
        {
          type:    "lang",
          regex:   RESOURCE_LINK_SHORTCODE_REGEX,
          replace: (s: string) => {
            const shortcode = Shortcode.fromString(s)
            const uuid = shortcode.get(0)
            const text = escapeShortcodes(shortcode.get(1) ?? "")
            const fragment = shortcode.get(2)
            const encoded = fragment ?
              encodeShortcodeArgs(uuid, fragment) :
              encodeShortcodeArgs(uuid)
            return `<a class="${RESOURCE_LINK_CKEDITOR_CLASS}" data-uuid="${encoded}">${text}</a>`
          }
        }
      ]
    }
  }

  get turndownRules(): TurndownRule[] {
    return [
      {
        name: RESOURCE_LINK,
        rule: {
          filter: function(node) {
            return (
              node.nodeName === "A" &&
              node.className === RESOURCE_LINK_CKEDITOR_CLASS
            )
          },
          replacement: (_content: string, node: Turndown.Node): string => {
            const [uuid, anchor] = decodeShortcodeArgs(
              (node as any).getAttribute("data-uuid") as string
            )

            const text = _content

            if (text === null) return ""

            return Shortcode.resourceLink(uuid, text, anchor).toHugo()
          }
        }
      }
    ]
  }
}
