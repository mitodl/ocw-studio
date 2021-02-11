import { html2md, md2html, YOUTUBE_EMBED_CLASS } from "./markdown"

describe("markdown library", () => {
  describe("youtube shortcode", () => {
    const YOUTUBE_TEST_MARKDOWN = '{{< youtube "2XID_W4neJo" >}}'

    it("should render to a section", () => {
      expect(md2html(YOUTUBE_TEST_MARKDOWN)).toBe(
        `<section class="${YOUTUBE_EMBED_CLASS}">2XID_W4neJo</section>`
      )
    })

    it("should support lossless bi-directional conversion", () => {
      expect(html2md(md2html(YOUTUBE_TEST_MARKDOWN))).toBe(
        YOUTUBE_TEST_MARKDOWN
      )
    })
  })
})
