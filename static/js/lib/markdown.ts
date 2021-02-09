import { Converter } from "showdown"

const YOUTUBE_SHORTCODE_REGEX = /{{ youtube "(\S+)" }}/

function youtubeShortcodeExtension() {
  return [{
  type: "lang",
  regex:YOUTUBE_SHORTCODE_REGEX,
  replace: (s: string, match: string) => (
    `<iframe
      width="560"
      height="315"
      src="https://www.youtube.com/embed/${match}"
      frameborder="0"
      allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
      allowfullscreen>
    </iframe>`
  )
}]
}

const converter = new Converter({
  extensions: [youtubeShortcodeExtension]
})

export function html2md (html: string): string {
  return converter.makeMarkdown(html)
}

export function md2html (md: string): string {
  return converter.makeHtml(md)
}
