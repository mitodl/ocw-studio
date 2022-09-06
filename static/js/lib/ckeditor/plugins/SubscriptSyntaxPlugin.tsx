import Turndown from "turndown"
import Showdown from "showdown"

import MarkdownSyntaxPlugin from "./MarkdownSyntaxPlugin"
import { TurndownRule } from "../../../types/ckeditor_markdown"
import { Shortcode } from "./util"


const SUBSCRIPT_REGEX = Shortcode.regex("subscript", true)

export default class SubscriptSyntaxPlugin extends MarkdownSyntaxPlugin {
  static get pluginName(): string {
    return "SubscriptSyntaxPlugin"
  }


  get showdownExtension() {
    return function subscriptExtension(): Showdown.ShowdownExtension[] {
      return [
        {
          type:    "lang",
          regex:   SUBSCRIPT_REGEX,
          replace: (s :string) => {
            const value = Shortcode.fromString(s).get("content")
            // eslint-disable-next-line no-debugger
            return `<sub class='subscript'>${value}</sub>`
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
            return (node.nodeName === "SUB")
          },
          replacement: (content: string, _: Turndown.Node): string => {
            const text = content
            const v = Shortcode.toSubscript(text).toHugo()
            return v
          }
        }
      }
    ]
  }
}
