import TablePlugin from "@ckeditor/ckeditor5-table/src/table"
import ParagraphPlugin from "@ckeditor/ckeditor5-paragraph/src/paragraph"

import DisallowNestedTables from "./DisallowNestedTables"
import { createTestEditor } from "./test_util"

/**
 * Characterization test. Pins the schema rule so that a change to CKEditor's
 * addChildCheck contract surfaces here rather than as nestable tables in the
 * editor.
 */
const getEditor = createTestEditor([
  ParagraphPlugin,
  TablePlugin,
  DisallowNestedTables,
])

describe("DisallowNestedTables", () => {
  it("allows a table at the document root", async () => {
    const editor = await getEditor("")
    expect(editor.model.schema.checkChild(["$root"], "table")).toBe(true)
    await editor.destroy()
  })

  it("disallows a table nested inside a table cell", async () => {
    const editor = await getEditor("")
    expect(
      editor.model.schema.checkChild(
        ["$root", "table", "tableRow", "tableCell"],
        "table",
      ),
    ).toBe(false)
    await editor.destroy()
  })
})
