import { ShowdownExtension } from "showdown"
import MarkdownSyntaxPlugin from "./MarkdownSyntaxPlugin"
import { TurndownRule } from "../../../types/ckeditor_markdown"

const prepareTexForMarkdown = (s: string) => {
  return (
    s
      /**
       * CKEditor seems to be adding non-breaking spaces to the HTML sometimes.
       * We don't want these converted into HTML &nbsp; entities in the
       * markdown
       */
      .replace(/[^\S\r\n]/g, " ")
      /**
       * In TeX, a double backslash "\\" represents a newline. Markdown allows
       *  escaping a backslash. So in Markdown, a double backslash is equivalent
       *  to a single backslash.
       *
       *  So replace all double backslashes with a quadruple backslash.
       */
      .replace(/\\\\/g, String.raw`\\\\`)
  )
}

class MathSyntax extends MarkdownSyntaxPlugin {
  static get pluginName(): string {
    return "MathSyntax"
  }

  get showdownExtension() {
    return (): ShowdownExtension[] => {
      return [
        /**
         * Showdown has two types of extensions:
         *  - "lang"  ... called BEFORE the main md -> html conversion
         *  - "output" ... called AFTER the main md -> html conversion
         * See https://github.com/showdownjs/showdown/wiki/extensions#type-propertyrequired
         *
         * In LaTeX,
         *  - \(...\) represents INLINE math
         *  - \[...\] represents DISPLAY (block) math
         *
         * Why use types extension types? Two reasons:
         *  1. *Math at beginning of lines*: If a line begins with math, then
         *    that math should be included in the output html p tags:
         *
         *    md:   `\(E=mc^2\) math at beginning`
         *    html: <p><script type="math/tex">\(E=mc^2\)</script> math at beginning</p>
         *
         *    But Showdown treats <script> elements as block: They won't begin
         *    a paragraph. So we can't convert to a script tag in the lang
         *    extension. Instead, convert to a <span> and convert that to a
         *    script tag during output extension.
         *  2. Additionally, I was having issues with math at the END of a line
         *     when using only a lang extension. Never fully understood why.
         *
         * Added an extra backlash to make it work with ocw-hugo-themes, where
         * markdown allows escaping parentheses, so literal `\(` must be entered
         * as `\\(`.
         */
        {
          type: "lang",
          regex: /\\\\\((.*?)\\\\\)/g,
          replace: (_stringMatch: string, math: string) => {
            return `<span data-math="">${math}</span>`
          },
        },
        {
          type: "lang",
          regex: /\\\\\[(.*?)\\\\\]/g,
          replace: (_stringMatch: string, math: string) => {
            return `<span data-math="" mode="display">${math}</span>`
          },
        },
        {
          type: "output",
          regex: /<span data-math="">(.*?)<\/span>/g,
          replace: (_stringMatch: string, math: string) => {
            return `<script type="math/tex">${math}</script>`
          },
        },
        {
          type: "output",
          regex: /<span data-math="" mode="display">(.*?)<\/span>/g,
          replace: (_stringMatch: string, math: string) => {
            return `<script type="math/tex; mode=display">${math}</script>`
          },
        },
      ]
    }
  }

  get turndownRules(): TurndownRule[] {
    return [
      {
        name: "MathSyntaxRule",
        rule: {
          filter: (node) => {
            return (
              node instanceof HTMLScriptElement &&
              node.type.includes("math/tex")
            )
          },
          replacement: (_content: string, node): string => {
            // Use node.textContent not _content because we want
            // the unescaped version. E.g., \frac{1}{2}, not \\frac{1}{2}
            const script = node as HTMLScriptElement
            const isDisplayMode = script.type.includes("mode=display")
            const text = prepareTexForMarkdown(node.textContent ?? "")
            return isDisplayMode
              ? String.raw`\\[${text}\\]`
              : String.raw`\\(${text}\\)`
          },
        },
      },
    ]
  }
}

export default MathSyntax
