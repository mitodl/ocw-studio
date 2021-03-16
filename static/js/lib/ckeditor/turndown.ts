import { turndownService as ckeditorTurndownService } from "@ckeditor/ckeditor5-markdown-gfm/src/html2markdown/html2markdown"
import Turndown from "turndown"

export const turndownService = ckeditorTurndownService

export function html2md(html: string): string {
  return turndownService.turndown(html)
}

// the default is "*", which is strange
turndownService.options.bulletListMarker = "-"

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

    // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
    return rule.replacement!(content, node, options)
  } else {
    return "\n\n"
  }
}

// fix for the default behavior in turndown which, for some reason, adds
// extra spaces to the beginning of a list item. So it maps
// "<ul><li>item</li></ul>" -> "-   item" instead of "- item"
// see https://github.com/domchristie/turndown/issues/291
//
// eslint-disable-next-line @typescript-eslint/no-non-null-assertion
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
