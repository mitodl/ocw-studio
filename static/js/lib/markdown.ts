import { Converter } from "showdown"
import { turndownService } from "@ckeditor/ckeditor5-markdown-gfm/src/html2markdown/html2markdown"
import TurndownService from "turndown"

export function html2md(html: string): string {
  return turndownService.turndown(html)
}

// the default is "*", which is strange
turndownService.options.bulletListMarker = "-"

// fix for the default behavior in turndown which, for some reason, adds
// extra spaces to the beginning of a list item. So it maps
// "<ul><li>item</li></ul>" -> "-   item" instead of "- item"
// see https://github.com/domchristie/turndown/issues/291
turndownService.addRule("listItem", {
  filter:      "li",
  replacement: (
    content: string,
    node: TurndownService.Node,
    options: TurndownService.Options
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
})

const converter = new Converter()

export function md2html(md: string): string {
  return converter.makeHtml(md)
}
