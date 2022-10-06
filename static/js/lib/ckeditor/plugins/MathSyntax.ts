import { ShowdownExtension } from "showdown"
import MarkdownSyntaxPlugin from "./MarkdownSyntaxPlugin"
import { TurndownRule } from "../../../types/ckeditor_markdown"


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
         *    md:   `\(E=mc^2\) is cool`
         *    html: <p><script type="math/tex">\(E=mc^2\)</script> is cool </p>
         * 
         *    But Showdown treats <script> elements as block: They won't begin
         *    a paragraph. So we can't convert to a script tag in the lang
         *    extension. Instead, convert to a <span> and convert that to a
         *    script tag during output extension.
         *  2. Additionally, I was having issues with math at the END of a line
         *     when using only a lang extension. Never fully understood why.
         * We need to convert mathjax \(\) to script tags.
         *
         * Why use BOTH lang and output extensions?
         * Why use BOTH for mathjax? Because we want inputs like
         *
         * Added an extra backlash to make it work with ocw-hugo-themes
         */
        {
          type:    "lang",
          regex:   /\\\\\((.*?)\\\\\)/g,
          replace: (_stringMatch: string, math: string) => {
            return `<span data-math="">${math}</span>`
          }
        },
        {
          type:    "lang",
          regex:   /\\\\\[(.*?)\\\\\]/g,
          replace: (_stringMatch: string, math: string) => {
            return `<span data-math="" mode="display">${math}</span>`
          }
        },
        {
          type:    "output",
          regex:   /<span data-math="">(.*?)<\/span>/g,
          replace: (_stringMatch: string, math: string) => {
            return `<script type="math/tex">${math}</script>`
          }
        },
        {
          type:    "output",
          regex:   /<span data-math="" mode="display">(.*?)<\/span>/g,
          replace: (_stringMatch: string, math: string) => {
            return `<script type="math/tex; mode=display">${math}</script>`
          }
        }
      ]
    }
  }

  get turndownRules(): TurndownRule[] {
    return [
      {
        name: 'MathSyntaxRule',
        rule: {
          filter: node => {
            return node instanceof HTMLScriptElement && node.type.includes('math/tex')
          },
          replacement: (_content: string, node): string => {
            // Use node.textContent not _content because we want
            // the unescaped version. E.g., \frac{1}{2}, not \\frac{1}
            // @ts-ignore
            const isDisplayMode = node.type.includes('mode=display')
            return isDisplayMode ? String.raw`\\[${node.textContent}\\]` : String.raw`\\(${node.textContent}\\)`
          }
        }
      }
    ]
  }
}

export default MathSyntax
