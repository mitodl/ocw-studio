import { html2md, md2html, YOUTUBE_EMBED_CLASS } from './markdown'

describe('markdown library', () => {
  describe('youtube shortcode', () => {
    const YOUTUBE_TEST_MARKDOWN = '{{< youtube "2XID_W4neJo" >}}'

    it('should render to an iframe', () => {
      expect(md2html(YOUTUBE_TEST_MARKDOWN)).toBe(
        `<iframe
          width="560"
          class="${YOUTUBE_EMBED_CLASS}"
          height="315"
          src="https://www.youtube.com/embed/2XID_W4neJo"
          frameborder="0"
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
          allowfullscreen>
        </iframe>`.replace("\n", " ").replace(/\s+/g, ' '))
      })

    it('should support lossless bi-directional conversion', () => {
      expect(html2md(md2html(YOUTUBE_TEST_MARKDOWN))).toBe(YOUTUBE_TEST_MARKDOWN)
    })
  })
})
