import { html2md, md2html } from "./markdown"

import { TEST_MARKDOWN, markdownTest } from "../test_util"

describe("markdown library", () => {
  it("should support lossless bi-directional conversion", () => {
    expect(html2md(md2html(TEST_MARKDOWN))).toBe(TEST_MARKDOWN)
  })

  describe("html2md", () => {
    it("should not add extra spaces to the beginning of a list item", () => {
      markdownTest("- my item", "<ul><li>my item</li></ul>")
    })

    it("should do the right thing with nested lists", () => {
      markdownTest(
        "- first item\n    - nested item",
        "<ul><li>first item<ul><li>nested item</li></ul></li></ul>"
      )
    })
  })
})
