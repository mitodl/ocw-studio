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

  it("accepts id and baseUrl on the opening tag and drops them on save", async () => {
    const editor = await getEditor("")
    markdownTest(
      editor,
      [
        '{{< image-gallery id="3c45e491-599e-24a6-2f95-5e1517238299_nanogallery2" baseUrl="/courses/21g-049-french-photography-spring-2017/" >}}',
        '{{< image-gallery-item uuid="aaa" >}}',
        '{{< image-gallery-item uuid="bbb" >}}',
        "{{</ image-gallery >}}",
      ].join("\n"),
      '<div class="image-gallery" data-uuids="aaa,bbb"></div>',
      [
        "{{< image-gallery >}}",
        '{{< image-gallery-item uuid="aaa" >}}',
        '{{< image-gallery-item uuid="bbb" >}}',
        "{{< /image-gallery >}}",
      ].join("\n"),
    )
  })

  it("keeps two galleries in one document separate", async () => {
    const editor = await getEditor("")
    markdownTest(
      editor,
      [
        '{{< image-gallery id="first" >}}',
        '{{< image-gallery-item uuid="aaa" >}}',
        "{{< /image-gallery >}}",
        "",
        "Between the galleries.",
        "",
        '{{< image-gallery baseUrl="/courses/x/" >}}',
        '{{< image-gallery-item uuid="bbb" >}}',
        "{{< /image-gallery >}}",
      ].join("\n"),
      [
        '<div class="image-gallery" data-uuids="aaa"></div>',
        "<p>Between the galleries.</p>",
        '<div class="image-gallery" data-uuids="bbb"></div>',
      ].join("\n"),
      [
        "{{< image-gallery >}}",
        '{{< image-gallery-item uuid="aaa" >}}',
        "{{< /image-gallery >}}",
        "",
        "Between the galleries.",
        "",
        "{{< image-gallery >}}",
        '{{< image-gallery-item uuid="bbb" >}}',
        "{{< /image-gallery >}}",
      ].join("\n"),
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
