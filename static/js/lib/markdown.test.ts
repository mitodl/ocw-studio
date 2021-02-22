import { html2md, md2html } from "../../../ckeditor/lib/markdown"

const TEST_DATA = `## A heading

Amazing stuff! Paragraphs!

And another paragraph!

And here a youtube shortcode:

{{< youtube "2XIDW4neJo" >}}

**bold** and even _italic_ text.

*   a
*   list
*   of
*   items
*   including
*   [links](https://reactjs.org/docs/hooks-faq.html#how-can-i-measure-a-dom-node)

also have some

> block quotes

good stuff.`

describe("markdown library", () => {
  describe("general markdown support", () => {
    it("should support lossless bi-directional conversion", () => {
      expect(html2md(md2html(TEST_DATA)).replace("\\", "")).toBe(TEST_DATA)
    })
  })
})
