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
// @ts-ignore also typing for `rules.blankRule` is incorrect
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
    return rule.replacement!(content, node, options)
  } else {
    return "\n\n"
  }
}

// fix for the default behavior in turndown which, for some reason, adds
// extra spaces to the beginning of a list item. So it maps
// "<ul><li>item</li></ul>" -> "-   item" instead of "- item"
// see https://github.com/domchristie/turndown/issues/291
turndownService.rules.array.find(rule => rule.filter === "li")!.replacement = (
  content: string,
  node: Turndown.Node,
  options: Turndown.Options
) => {
  content = content
    .replace(/^\n+/, "") // remove leading newlines
    .replace(/\n+$/, "\n") // replace trailing newlines with just a single one
    .replace(/\n/gm, "\n    ") // indent

  let prefix = `${options.bulletListMarker} `
  const parent = node.parentNode
  if (parent && parent.nodeName === "OL") {
    // @ts-ignore
    const start: string = parent.getAttribute("start")
    const index = Array.prototype.indexOf.call(parent.children, node)
    prefix = `${start ? Number(start) + index : index + 1}. `
  }
  return (
    prefix + content + (node.nextSibling && !/\n$/.test(content) ? "\n" : "")
  )
}
