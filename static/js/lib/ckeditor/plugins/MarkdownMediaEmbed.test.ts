import MarkdownMediaEmbed, { YOUTUBE_URL_REGEX } from "./MarkdownMediaEmbed"
import Markdown from "./Markdown"
import { createTestEditor, markdownTest } from "./test_util"
import { turndownService } from "../turndown"

const getEditor = createTestEditor([MarkdownMediaEmbed, Markdown])

describe("MarkdownMediaEmbed plugin", () => {
  afterEach(() => {
    turndownService.rules.array = turndownService.rules.array.filter(
      (rule: any) => rule.filter !== "figure"
    )
    // @ts-ignore
    turndownService._customRulesSet = undefined
  })

  it("should output youtube shortcode when given youtube shortcode", async () => {
    const editor = await getEditor("{{< youtube LzC8c0Crpys >}}")
    // @ts-ignore
    expect(editor.getData()).toBe("{{< youtube LzC8c0Crpys >}}")
  })

  it("should provide markdown support for YouTube shortcodes", async () => {
    const editor = await getEditor()
    markdownTest(
      editor,
      "{{< youtube LzC8c0Crpys >}}",
      `<figure class="media">
        <oembed url="https://www.youtube.com/watch?v=LzC8c0Crpys">
        </oembed>
      </figure>`
    )
  })

  it("should put adjacent youtube shortcodes on separate lines", async () => {
    const editor = await getEditor()
    markdownTest(
      editor,
      "{{< youtube LzC8c0Crpys >}}\n{{< youtube rQMZKyaYeSc >}}",
      `<figure class="media">
        <oembed url="https://www.youtube.com/watch?v=LzC8c0Crpys">
        </oembed>
      </figure>
      <figure class="media">
        <oembed url="https://www.youtube.com/watch?v=rQMZKyaYeSc">
        </oembed>
      </figure>`
    )
  })

  it("should load a youtube video in a previewable iframe in the editing UI", async () => {
    const editor = await getEditor("{{< youtube LzC8c0Crpys >}}")
    // @ts-ignore
    const iframe = editor.ui.view.editable.element.querySelector("iframe")
    expect(iframe.getAttribute("src")).toBe(
      "https://www.youtube.com/embed/LzC8c0Crpys"
    )
  })

  describe("youtube regex", () => {
    it("should pull out the video ID in a variety of scenarios", () => {
      [
        "https://www.youtube.com/watch?foo=potato&v=ENxbcvUXfnM",
        "https://youtube.com/watch?foo=potato&v=ENxbcvUXfnM&foobar=biznik",
        "https://www.youtube.com/watch?foo=potato&v=ENxbcvUXfnM&foobar",
        "http://www.youtube.com/watch?v=ENxbcvUXfnM&foobar",
        "https://www.youtube.com/watch?v=ENxbcvUXfnM&foobar",
        "http://www.youtube.com/watch?v=ENxbcvUXfnM&foobar",
        "https://youtube.com/watch?v=ENxbcvUXfnM&foobar",
        "http://youtube.com/watch?v=ENxbcvUXfnM&foobar",
        "youtube.com/watch?v=ENxbcvUXfnM",
        "https://youtu.be/ENxbcvUXfnM",
        "youtu.be/ENxbcvUXfnM"
      ].forEach(url => {
        // @ts-ignore
        expect(url.match(YOUTUBE_URL_REGEX)[1]).toBe("ENxbcvUXfnM")
      })
    })
  })
})
