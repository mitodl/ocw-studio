import { turndownService as ckeditorTurndownService } from "@ckeditor/ckeditor5-markdown-gfm/src/html2markdown/html2markdown"
import Turndown from "turndown"
import { TABLE_ELS } from "./plugins/constants"

export const turndownService = ckeditorTurndownService

export function ruleMatches(rule: Turndown.Rule, node: HTMLElement): boolean {
  const filter = rule.filter
  const nodeName = node.nodeName.toLowerCase() as Turndown.TagName

  if (typeof filter === "string") {
    return filter === nodeName
  }

  if (Array.isArray(filter)) {
    return filter.includes(nodeName)
  }

  if (typeof filter === "function") {
    return filter(node, {})
  }
  throw new TypeError("`filter` needs to be a string, array, or function")
}

// this removes all table-related rules
turndownService.rules.array = turndownService.rules.array.filter(rule => {
  const anyMatch = TABLE_ELS.some(el => {
    const element = document.createElement(el)
    document.body.appendChild(element)

    if (el === "table") {
      const thead = document.createElement("thead")
      const trow = document.createElement("tr")
      element.appendChild(thead)
      thead.appendChild(trow)
    }
    return ruleMatches(rule, element)
  })

  return !anyMatch
})

export function html2md(html: string): string {
  return turndownService.turndown(html)
}

// the default is "*", which is strange
turndownService.options.bulletListMarker = "-"

// The default is "_", which causes issues with MathJax
// Github issue for reference https://github.com/mitodl/ocw-hugo-themes/issues/501
turndownService.options.emDelimiter = "*"

// this is sort of a hack. Turndown marks certain nodes as "blank" and will
// then ignore rules defined for them. What we do here is intercept the
// handling of these 'blank' nodes so that we can use rules define for them if
// we need to.
//
// This problem arises notably with iframes and figure tags.
// see here for details:
// https://github.com/domchristie/turndown/issues/293
//
// @ts-expect-error also typing for `rules.blankRule` is incorrect
turndownService.rules.blankRule.replacement = (
  content: string,
  node: Turndown.Node,
  options: Turndown.Options
) => {
  const matchingRules = turndownService.rules.array.filter(
    rule => node.nodeName.toLowerCase() === rule.filter
  )

  if (matchingRules.length > 1) {
    throw new Error("should only be a single matching rule")
  }

  if (matchingRules.length === 1) {
    const [rule] = matchingRules
    return rule.replacement?.(content, node, options)
  } else {
    return "\n\n"
  }
}

// fix for the default behavior in turndown which, for some reason, adds
// extra spaces to the beginning of a list item. So it maps
// "<ul><li>item</li></ul>" -> "-   item" instead of "- item"
// see https://github.com/domchristie/turndown/issues/291
const itemRule = turndownService.rules.array.find(rule => rule.filter === "li")
if (!itemRule) {
  throw new Error("Expected rule to exist.")
}
itemRule.replacement = (
  content: string,
  node: Turndown.Node,
  options: Turndown.Options
) => {
  content = content
    .replace(/^\n+/, "") // remove leading newlines
    .replace(/\n+$/, "\n") // replace trailing newlines with just a single one
    .replace(/\n/gm, "\n    ") // indent

  let prefix = `${options.bulletListMarker} `
  const parent = node.parentElement
  if (parent && parent.nodeName === "OL") {
    const start = parent.getAttribute("start")
    const index = Array.prototype.indexOf.call(parent.children, node)
    prefix = `${start ? Number(start) + index : index + 1}. `
  }
  return (
    prefix + content + (node.nextSibling && !/\n$/.test(content) ? "\n" : "")
  )
}

const BASE_TURNDOWN_RULES = [...turndownService.rules.array]
const BASE_TURNDOWN_KEEP = [
  // @ts-expect-error `_keep` is not part of Turndown's public API, see `resetTurndownService` for more.
  ...turndownService.rules._keep
]
const BASE_TURNDOWN_KEEP_REPLACEMENT = turndownService.rules.keepReplacement

/**
 * CKEditor's markdown plugin uses a single Turndown instance. We occasionally
 * want to reset it to its initial state (e.g., for different editor instances).
 */
export const resetTurndownService = () => {
  turndownService.rules.array = [...BASE_TURNDOWN_RULES]

  /**
   * We need to access `_keep` in order to "reset" what HTML tags Turndown will
   * keep when converting HTML to Markdown. Turndown has a public API for
   * adding tags to its "keep" list, but not for removing tags or resetting its
   * list.
   */
  // @ts-expect-error `_keep` is not part of Turndown's public API, see above
  turndownService.rules._keep = [...BASE_TURNDOWN_KEEP]
  turndownService.rules.keepReplacement = BASE_TURNDOWN_KEEP_REPLACEMENT
}

/**
 * This class contains a few helpers that improve upon the default way in which
 * Turndown includes raw HTML tags in the markdown output.
 *
 * When converting HTML -> MD, Turndown generally ignores HTML tags that have no
 * markdown equivalent. (E.g., "span", "div", "sup", "sub", ...). This behavior
 * can be customized in two ways:
 *  1. its `keep` method tells Turndown which rules to keep
 *  2. its `keepReplacement` function tells Turndown HOW to replace those tags
 *
 * The default behavior of `keepReplacement` has two drawbacks.
 *
 * Issue #1
 * -----------
 * The default behavior can result in HTML tags beginning a markdown line that would
 * otherwise be a Markdown paragraph. For example:
 * ```js
 * const tds = new TurndownService()
 * tds.keep(["sup"])
 * tds.turndown("<p><sup>2</sup> Hello <strong>world</strong>!</p>")
 * // => "<sup>2</sup> Hello **world**!"
 * ```
 * The output above is bad because when an HTML tag begins a markdown line, it
 * begins a *block* of markdown, and subsequent characters on that line are
 * NOT treated as Markdown. Hence the `**` above would be rendered as literal
 * asterisks, not as bold.
 *
 * Issue #2
 * ------------
 * The default behavior is that the *content* of an HTML tag is not converted
 * to Markdown. This is problematic for tags that contain shortcode HTML. For
 * example, `<sup><a class="resource-link" data-uuid ... >2</a></sup>` should
 * really needs its content to be converted to markdown in order for Hugo to
 * recognize it as a shortcode.
 */
class TurndownHtmlHelpers {
  private turndownInstance: Turndown

  constructor(turndown: Turndown) {
    this.turndownInstance = turndown
  }

  /**
   * This function improves upon Turndown's default rule for including raw HTML
   * tags in Markdown. In particular, it:
   *  - ensures that the child content of an inline HTML node is also converted, which
   *    we need in case the child content contains shortcode.
   *  - ensures that an inline HTML tag never begins a line of Markdown.
   */
  keepReplacer: Turndown.ReplacementFunction = (content, node) => {
    /**
     * "isBlock" is a Turndown-specific addition to the DOM node interface.
     * It appears to be part of their public API in that the author recommends
     * using it in several issues.
     */
    const el = node as HTMLElement & { isBlock: boolean }

    if (el.isBlock) {
      throw new Error("Inclusion of block content not yet supported.")
    }

    /**
     * Now convert the node's child content to Markdown.
     * This addresses Issue #2 above.
     */
    const clone = el.cloneNode() as HTMLElement
    clone.innerHTML = this.turndown(el.innerHTML)

    /**
     * To address Issue #1, we'll mark places where HTML is inserted. Later, we
     * can remove all the markings except the ones that begin a new line.
     */
    return `<raw_html_follows/>${clone.outerHTML}`
  }

  turndown = (html: string) =>
    this.turndownInstance
      .turndown(html)
      .replace(/^[ ]*<raw_html_follows\/>/g, "\u200b")
      .replace(/<raw_html_follows\/>/g, "")
}

export const turndownHtmlHelpers = new TurndownHtmlHelpers(turndownService)
