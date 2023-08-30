import Turndown from "turndown"
import Showdown from "showdown"

import MarkdownSyntaxPlugin from "./MarkdownSyntaxPlugin"
import { TurndownRule } from "../../../types/ckeditor_markdown"
import { buildAttrsString } from "./util"

import { TABLE_ELS, ATTRIBUTE_REGEX, CONTENT_TABLE_ELS } from "./constants"

type Position = "open" | "close"

const handleContentWhitespace = (content: string) =>
  `${content.startsWith("\n") ? "" : "\n"}${content}${
    content.endsWith("\n") ? "" : "\n"
  }`

export default class TableMarkdownSyntax extends MarkdownSyntaxPlugin {
  static get pluginName(): string {
    return "TableMarkdownSyntax"
  }

  get showdownExtension() {
    return function tableExtension(): Showdown.ShowdownExtension[] {
      return TABLE_ELS.map((el) => {
        const shortcodeRegex = new RegExp(`{{< ${el}(open|close).*? >}}`, "g")

        return {
          type: "lang",
          regex: shortcodeRegex,
          replace: (_s: string, position: Position) => {
            const attrs = _s.match(ATTRIBUTE_REGEX)
            return position === "open"
              ? `<${el}${buildAttrsString(attrs)}>`
              : `</${el}>`
          },
        }
      })
    }
  }

  get turndownRules(): TurndownRule[] {
    return [
      {
        name: "TableMarkdownSyntax",
        rule: {
          filter: TABLE_ELS,
          replacement: (content: string, node: Turndown.Node): string => {
            const name = node.nodeName.toLowerCase()
            const el = node as HTMLElement
            const attributes = el.hasAttributes()
              ? buildAttrsString(
                  Array.from(el.attributes).map(
                    (attr) => `${attr.name}="${attr.value}"`,
                  ),
                )
              : ""

            const processedContent = CONTENT_TABLE_ELS.includes(name)
              ? handleContentWhitespace(content)
              : content

            return `{{< ${name}open${attributes} >}}${processedContent}{{< ${name}close >}}`
          },
        },
      },
    ]
  }
}
