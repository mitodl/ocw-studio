import Turndown from "turndown"
import Showdown from "showdown"

import MarkdownSyntaxPlugin from "./MarkdownSyntaxPlugin"
import { TurndownRule } from "../../../types/ckeditor_markdown"
import { buildAttrsString } from "./util"

import { TABLE_ELS, ATTRIBUTE_REGEX } from "./constants"

type Position = "open" | "close"

export default class TableMarkdownSyntax extends MarkdownSyntaxPlugin {
  static get pluginName(): string {
    return "TableMarkdownSyntax"
  }

  get showdownExtension() {
    return function tableExtension(): Showdown.ShowdownExtension[] {
      return TABLE_ELS.map(el => {
        const shortcodeRegex = new RegExp(`{{< ${el}(open|close).*? >}}`, "g")

        return {
          type:    "lang",
          regex:   shortcodeRegex,
          replace: (_s: string, position: Position) => {
            const attrs = _s.match(ATTRIBUTE_REGEX)
            return position === "open" ?
              `<${el}${buildAttrsString(attrs)}>` :
              `</${el}>`
          }
        }
      })
    }
  }

  get turndownRules(): TurndownRule[] {
    return [
      {
        name: "TableMarkdownSyntax",
        rule: {
          filter:      TABLE_ELS,
          replacement: (content: string, node: Turndown.Node): string => {
            const name = node.nodeName.toLowerCase()
            const attributes = (node as HTMLElement).hasAttributes() ?
              buildAttrsString(
                //@ts-ignore
                Array.from(node.attributes).map(
                  //@ts-ignore
                  attr => `${attr.name}="${attr.value}"`
                )
              ) :
              ""
            return `{{< ${name}open${attributes} >}}${content}{{< ${name}close >}}`
          }
        }
      }
    ]
  }
}
