import ResourceLink from "./ResourceLink"
import Markdown from "./Markdown"
import { createTestEditor, markdownTest } from "./test_util"
import { turndownService } from "../turndown"

const getEditor = createTestEditor([ResourceLink, Markdown])

describe("ResourceLink plugin", () => {
  afterEach(() => {
    turndownService.rules.array = turndownService.rules.array.filter(
      (rule: any) => rule.filter !== "span"
    )
    // @ts-ignore
    turndownService._customRulesSet = undefined
  })

  it("should take in and return 'resource' shortcode", async () => {
    const editor = await getEditor("{{< resource_link 1234567890 >}}")
    // @ts-ignore
    expect(editor.getData()).toBe("{{< resource_link 1234567890 >}}")
  })

  it("should serialize to and from markdown", async () => {
    const editor = await getEditor("")
    markdownTest(
      editor,
      "{{< resource_link asdfasdfasdfasdf >}}",
      '<p><span class="resource-link" data-uuid="asdfasdfasdfasdf"></span></p>'
    )
  })
})
