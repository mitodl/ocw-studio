import { ShowdownExtension } from "showdown"
import { TurndownRule } from "../../../types/ckeditor_markdown"
import MarkdownSyntaxPlugin from "./MarkdownSyntaxPlugin"

/**
 * This "extension" is addresses an incompatibility between
 *  - the HTML that showdown produces for lists
 *  - the HTML that CKEditor expects for lists
 *
 * When a markdown list item contains multiple lines, showdown puts <p> tags
 * around all list items (and multiple <p> tags for the multi-line list item).
 * See https://github.com/showdownjs/showdown/wiki/Showdown's-Markdown-syntax#known-differences-and-gotchas.
 *
 * CKEditor, on the other hand, forbids paragraphs inside list items. Both are
 * "block" elements in its schema; see https://ckeditor.com/docs/ckeditor5/latest/framework/guides/deep-dive/schema.html#defining-additional-semantics
 * and block elements cannot contain other block elements. (There is discussion
 * of having a list variant that can contain block elements; see
 * https://github.com/ckeditor/ckeditor5/issues/2973 for more.)
 *
 * So here we add a Showdown rule to replace list item paragraph tags with
 * linebreaks, the same as CKEditor produces.
 *
 */
export default class MarkdownListSyntax extends MarkdownSyntaxPlugin {
  get showdownExtension(): () => ShowdownExtension[] {
    return () => [
      {
        type:   "output",
        filter: htmlString => {
          const container = document.createElement("div")
          container.innerHTML = htmlString

          container.querySelectorAll("li > p").forEach(node => {
            const suffix = node.nextSibling === null ? "" : " <br><br>"
            node.outerHTML = `${node.innerHTML}${suffix}`
          })

          return container.innerHTML
        }
      }
    ]
  }

  get turndownRules(): TurndownRule[] {
    return []
  }
}
