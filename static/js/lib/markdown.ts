import { Converter } from "showdown"
import TurndownService from "turndown"
import { turndownService } from "@ckeditor/ckeditor5-markdown-gfm/src/html2markdown/html2markdown"

export const YOUTUBE_SHORTCODE_REGEX = /{{< youtube "(\S+)" >}}/
export const YOUTUBE_SRC_REGEX = /https:\/\/www\.youtube\.com\/embed\/(\S+)\/?$/
export const YOUTUBE_EMBED_CLASS = "youtube-embed"

export const youtubeEmbedUrl = (videoId: string): string =>
  `https://www.youtube.com/embed/${videoId}`

export const YOUTUBE_EMBED_PARAMS = {
  width:       "560",
  height:      "315",
  frameborder: "0",
  allow:
    "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture",
  allowfullscreen: true
}

function youtubeShortcodeExtension() {
  return [
    {
      type:    "lang",
      regex:   YOUTUBE_SHORTCODE_REGEX,
      replace: (s: string, match: string) =>
        `<section class="${YOUTUBE_EMBED_CLASS}">${match}</section>`
    }
  ]
}

turndownService.addRule("youtubeEmbed", {
  filter: (node: any, options: any) => {
    return (
      node.nodeName === "SECTION" &&
      node.getAttribute("class") === YOUTUBE_EMBED_CLASS
    )
  },
  replacement: (
    content: string,
    node: TurndownService.Node,
    options: any
  ): string => {
    const videoId = content.replace(/\\/, "")
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
