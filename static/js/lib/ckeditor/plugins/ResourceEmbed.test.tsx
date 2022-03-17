import ResourceEmbed from "./ResourceEmbed"
import Markdown from "./Markdown"
import { createTestEditor, markdownTest, getConverters } from "./test_util"
import { turndownService } from "../turndown"

const getEditor = createTestEditor([ResourceEmbed, Markdown])

describe("ResourceEmbed plugin", () => {
  afterEach(() => {
    turndownService.rules.array = turndownService.rules.array.filter(
      (rule: any) => rule.filter !== "figure" && rule.filter !== "section"
    )
    // @ts-ignore
    turndownService._customRulesSet = undefined
  })

  it("should take in and return 'resource' shortcode", async () => {
    const editor = await getEditor("{{< resource 1234567890 >}}")
    // @ts-ignore
    expect(editor.getData()).toBe("{{< resource 1234567890 >}}")
  })

  it("should serialize to and from markdown", async () => {
    const editor = await getEditor("")
    markdownTest(
      editor,
      "{{< resource asdfasdfasdfasdf >}}",
      '<section data-uuid="asdfasdfasdfasdf"></section>'
    )
  })

  it("should tolerate quotation marks around its argument", async () => {
    const editor = await getEditor("")
    // This conversion is not quite lossless. We lose the optional quotes around
    // shortcode argument.
    const { md2html } = getConverters(editor)
    expect(md2html('{{< resource "asdfasdfasdfasdf" >}}')).toBe(
      '<section data-uuid="asdfasdfasdfasdf"></section>'
    )
  })
})
