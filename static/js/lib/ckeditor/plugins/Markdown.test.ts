import Markdown, { MarkdownDataProcessor } from "./Markdown"

import { createTestEditor, markdownTest } from "./test_util"
import { turndownService } from "../turndown"

import { TEST_MARKDOWN, TEST_HTML } from "../../../test_constants"

const getEditor = createTestEditor([Markdown])

describe("Markdown CKEditor plugin", () => {
  it("should have a name", () => {
    expect(Markdown.pluginName).toBe("Markdown")
  })

  describe("basic Markdown support", () => {
    it("should set custom rules flag after instantiation", async () => {
      await getEditor("")
      // @ts-ignore
      expect(turndownService._customRulesSet).toBeTruthy()
    })

    it("should set editor.data.processor", async () => {
      const editor = await getEditor("")
      expect(editor.data.processor).toBeInstanceOf(MarkdownDataProcessor)
    })

    it("should provide for bi-directional translation", async () => {
      const editor = await getEditor("")
      markdownTest(editor, TEST_MARKDOWN, TEST_HTML)
    })
  })

  describe("tables", () => {
    it("should support tables", async () => {
      // TODO why is this passing at the turndown level but failing here?
      //
      // figured it out: Tables MUST have a `thead` with `th` elements in it, otherwise turndown doesn't seem to know what to do
      const editor = await getEditor("")
      markdownTest(
        editor,
        "| Heading 1 | Heading 2 |\n" +
          "| --- | --- |\n" +
          "| Cell 1 | Cell 2 |\n" +
          "| Cell 3 | Cell 4 |",
        "<table>" +
          "<thead>" +
          "<tr>" +
          "<th>Heading 1</th>" +
          "<th>Heading 2</th>" +
          "</tr>" +
          "</thead>" +
          "<tbody>" +
          "<tr>" +
          "<td>Cell 1</td>" +
          "<td>Cell 2</td>" +
          "</tr>" +
          "<tr>" +
          "<td>Cell 3</td>" +
          "<td>Cell 4</td>" +
          "</tr>" +
          "</tbody>" +
          "</table>"
      )
    })
  })
})
