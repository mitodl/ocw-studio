import Markdown, { MarkdownDataProcessor } from "./Markdown"

import { createTestEditor, markdownTest } from "./test_util"
import { turndownService } from "../turndown"

import { TEST_MARKDOWN, TEST_HTML } from "../../../test_constants"

describe("Markdown CKEditor plugin", () => {
  it("should have a name", () => {
    expect(Markdown.pluginName).toBe("Markdown")
  })

  describe("basic Markdown support", () => {
    it("should set custom rules flag after instantiation", async () => {
      await createTestEditor([Markdown])
      // @ts-ignore
      expect(turndownService._customRulesSet).toBeTruthy()
    })

    it("should set editor.data.processor", async () => {
      const editor = await createTestEditor([Markdown])
      expect(editor.data.processor).toBeInstanceOf(MarkdownDataProcessor)
    })

    it("should provide for bi-directional translation", async () => {
      const editor = await createTestEditor([Markdown])
      markdownTest(editor, TEST_MARKDOWN, TEST_HTML)
    })
  })
})
