import MediaEmbed from "@ckeditor/ckeditor5-media-embed/src/mediaembed"
import Plugin from "@ckeditor/ckeditor5-core/src/plugin"
import Turndown from "turndown"
import Showdown from "showdown"

import MarkdownSyntaxPlugin from "./MarkdownSyntaxPlugin"
import { TurndownRule } from "../../../types/ckeditor_markdown"

export const YOUTUBE_SHORTCODE_REGEX = /{{< youtube (\S+) >}}/g

export const EMBED_CLASS = "media"

export const YOUTUBE_URL_REGEX = /(?:youtube\.com\/watch\?\S*v=|youtu.be\/)([a-zA-Z0-9_]+)/

class MediaEmbedMarkdownSyntax extends MarkdownSyntaxPlugin {
  get showdownExtension() {
    return function mediaEmbedExtension(): Showdown.ShowdownExtension[] {
      return [
        {
          type:    "lang",
          regex:   YOUTUBE_SHORTCODE_REGEX,
          replace: (s: string, match: string) =>
            `<figure class="${EMBED_CLASS}">
              <oembed url="https://www.youtube.com/watch?v=${match}">
              </oembed>
            </figure>`
        }
      ]
    }
  }

  get turndownRule(): TurndownRule {
    return {
      name: "mediaEmbed",
      rule: {
        filter:      "figure",
        replacement: (
          content: string,
          node: Turndown.Node,
          _: Turndown.Options
        ): string => {
          const videoId = node
            ?.querySelector("oembed")
            ?.getAttribute("url")
            ?.match(YOUTUBE_URL_REGEX)

          if (videoId && videoId[1]) {
            return `{{< youtube ${videoId[1]} >}}\n`
          } else {
            return "\n\n"
          }
        }
      }
    }
  }
}

export default class MarkdownMediaEmbed extends Plugin {
  static get requires(): Plugin[] {
    return [MediaEmbed, MediaEmbedMarkdownSyntax]
  }
}
