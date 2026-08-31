import ImageGallery from "./ImageGallery"
import Markdown from "./Markdown"
import { createTestEditor, markdownTest } from "./test_util"
import { turndownService } from "../turndown"

const getEditor = createTestEditor([ImageGallery, Markdown])

describe("ImageGallery plugin", () => {
  afterEach(() => {
    turndownService.rules.array = turndownService.rules.array.filter(
      (rule: any) => rule.filter !== "figure" && rule.filter !== "section",
    )
  })

  it("round-trips a gallery with a single image", async () => {
    const editor = await getEditor("")
    markdownTest(
      editor,
      [
        "{{< image-gallery >}}",
        '{{< image-gallery-item uuid="uuid-one" >}}',
        "{{< /image-gallery >}}",
      ].join("\n"),
      '<div class="image-gallery" data-uuids="uuid-one"></div>',
    )
  })

  it("round-trips a gallery with several images, preserving order", async () => {
    const editor = await getEditor("")
    markdownTest(
      editor,
      [
        "{{< image-gallery >}}",
        '{{< image-gallery-item uuid="ccc" >}}',
        '{{< image-gallery-item uuid="aaa" >}}',
        '{{< image-gallery-item uuid="bbb" >}}',
        "{{< /image-gallery >}}",
      ].join("\n"),
      '<div class="image-gallery" data-uuids="ccc,aaa,bbb"></div>',
    )
  })

  it("keeps surrounding prose intact", async () => {
    const editor = await getEditor("")
    markdownTest(
      editor,
      [
        "Here is a gallery.",
        "",
        "{{< image-gallery >}}",
        '{{< image-gallery-item uuid="aaa" >}}',
        "{{< /image-gallery >}}",
        "",
        "And some text after it.",
      ].join("\n"),
      [
        "<p>Here is a gallery.</p>",
        '<div class="image-gallery" data-uuids="aaa"></div>',
        "<p>And some text after it.</p>",
      ].join("\n"),
    )
  })

  it("loads a gallery into the editor and writes it back unchanged", async () => {
    const markdown = [
      "{{< image-gallery >}}",
      '{{< image-gallery-item uuid="aaa" >}}',
      '{{< image-gallery-item uuid="bbb" >}}',
      "{{< /image-gallery >}}",
    ].join("\n")
    const editor = await getEditor(markdown)
    expect(editor.getData()).toBe(markdown)
  })

  it("drops an empty gallery rather than writing a broken shortcode", async () => {
    const editor = await getEditor("")
    const { html2md } = editor.data.processor as any
    expect(html2md('<div class="image-gallery" data-uuids=""></div>')).toBe("")
  })
})
