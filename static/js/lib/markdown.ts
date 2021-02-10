import { Converter } from "showdown"
import TurndownService from "turndown"
import { gfm } from "turndown-plugin-gfm"

const turndownService = new TurndownService({
  codeBlockStyle: "fenced",
  hr:             "---",
  headingStyle:   "atx"
})

turndownService.use(gfm)

const YOUTUBE_SHORTCODE_REGEX = /{{< youtube "(\S+)" >}}/
const YOUTUBE_SRC_REGEX = /https:\/\/www\.youtube\.com\/embed\/(\S+)\/?$/
export const YOUTUBE_EMBED_CLASS = "youtube-embed"

function youtubeShortcodeExtension() {
  return [
    {
      type:    "lang",
      regex:   YOUTUBE_SHORTCODE_REGEX,
      replace: (s: string, match: string) =>
        `<iframe
      width="560"
      class="${YOUTUBE_EMBED_CLASS}"
      height="315"
      src="https://www.youtube.com/embed/${match}"
      frameborder="0"
      allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
      allowfullscreen>
    </iframe>`
          .replace("\n", " ")
          .replace(/\s+/g, " ")
    }
  ]
}

turndownService.addRule("youtubeEmbed", {
  filter: (node, options) =>
    node.nodeName === "IFRAME" &&
    node.getAttribute("class") === YOUTUBE_EMBED_CLASS,
  replacement: (
    content: string,
    node: TurndownService.Node,
    options
  ): string => {
    const src: string = (node as any).getAttribute("src")
    const match = src.match(YOUTUBE_SRC_REGEX)
    const videoId = match ? match[1] : ""
    return `{{< youtube "${videoId}" >}}`
  }
})

export function html2md(html: string): string {
  return turndownService.turndown(html)
}

const converter = new Converter({
  extensions: [youtubeShortcodeExtension]
})

export function md2html(md: string): string {
  return converter.makeHtml(md)
}
