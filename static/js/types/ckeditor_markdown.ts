import Turndown from "turndown"
import Showdown from "showdown"

export interface TurndownRule {
  name: string
  rule: Turndown.Rule
}

export interface MarkdownConfig {
  showdownExtensions: Array<() => Showdown.ShowdownExtension[]>
  turndownRules: TurndownRule[]
  allowedHtml: (keyof HTMLElementTagNameMap)[]
}
