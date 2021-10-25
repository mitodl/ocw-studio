import Turndown from "turndown"
import Showdown from "showdown"

import MarkdownSyntaxPlugin from "./MarkdownSyntaxPlugin"
import { TurndownRule } from "../../../types/ckeditor_markdown"

import { TABLE_ELS } from "./constants"

type Position = "open" | "close"

export default class TableMarkdownSyntax extends MarkdownSyntaxPlugin {
  static get pluginName(): string {
    return "TableMarkdownSyntax"
  }

  get showdownExtension() {
    return function resourceExtension(): Showdown.ShowdownExtension[] {
      return TABLE_ELS.map(el => {
        const shortcodeRegex = new RegExp(`{{< ${el}(open|close) >}}`, "g")

        return {
          type:    "lang",
          regex:   shortcodeRegex,
          replace: (_s: string, position: Position) => {
            return position === "open" ? `<${el}>` : `</${el}>`
          }
        }
      })
    }
  }

  get turndownRule(): TurndownRule {
    return {
      name: "TableMarkdownSyntax",
      rule: {
        filter:      TABLE_ELS,
        replacement: (content: string, node: Turndown.Node): string => {
          const name = node.nodeName.toLowerCase()
          const normalizedContent = content.replace("\n\n", "\n")
          return `{{< ${name}open >}}${normalizedContent}{{< ${name}close >}}`
        }
      }
    }
  }
}
