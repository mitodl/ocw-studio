import Turndown from "turndown"
import Showdown from "showdown"

import MarkdownSyntaxPlugin from "./MarkdownSyntaxPlugin"
import { TurndownRule } from "../../../types/ckeditor_markdown"

export default class SubscriptSyntaxPlugin extends MarkdownSyntaxPlugin {
  static get pluginName(): string {
    return "SubscriptSyntaxPlugin"
  }

  get showdownExtension() {
    return function subscriptExtension(): Showdown.ShowdownExtension[] {
      return [
        {
          type:    "lang",
          // eslint-disable-next-line no-useless-escape
          regex:   new RegExp(/\\\(\s+_{\w+}_\s+\\\)/),
          replace: (s: string) => {
            const value = s.match("(?<=_{)(.*)(?=})")
            // eslint-disable-next-line no-debugger
            return `<sub class='subscript'>${value ? value[0] : ""}</sub>`
          }
        }
      ]
    }
  }

  get turndownRules(): TurndownRule[] {
    return [
      {
        name: "SubscriptSyntaxPlugin",
        rule: {
          filter: function(node) {
            return node.nodeName === "SUB"
          },
          replacement: (content: string, _: Turndown.Node): string => {
            const v = `\\( _{${content}} \\)`
            return v
          }
        }
      }
    ]
  }
}
