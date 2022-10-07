import ResourceEmbed from "./ResourceEmbed"
import Markdown from "./Markdown"
import { createTestEditor, markdownTest } from "./test_util"
import { turndownService } from "../turndown"

const getEditor = createTestEditor([ResourceEmbed, Markdown])

describe("ResourceEmbed plugin", () => {
  afterEach(() => {
    turndownService.rules.array = turndownService.rules.array.filter(
      (rule: any) => rule.filter !== "figure" && rule.filter !== "section"
    )
  })

  it("should take in and return 'resource' shortcode", async () => {
    const editor = await getEditor("{{< resource 1234567890 >}}")
    expect(editor.getData()).toBe('{{< resource uuid="1234567890" >}}')
  })

  it.each([
    "{{< resource asdfasdfasdfasdf >}}",
    '{{< resource "asdfasdfasdfasdf" >}}'
  ])("should serialize to and from markdown", async markdown => {
    const editor = await getEditor("")
    markdownTest(
      editor,
      markdown,
      '<section data-uuid="asdfasdfasdfasdf"></section>',
      '{{< resource uuid="asdfasdfasdfasdf" >}}'
    )
  })

  it("preserves href params", async () => {
    const editor = await getEditor("")
    markdownTest(
      editor,
      '{{< resource uuid="asdfasdfasdfasdf" href="https://www.mit.edu" >}}',
      '<section data-href="https://www.mit.edu" data-uuid="asdfasdfasdfasdf"></section>'
    )
  })

  it("preserves href_uuid params", async () => {
    const editor = await getEditor("")
    markdownTest(
      editor,
      '{{< resource uuid="asdfasdfasdfasdf" href_uuid="abcwxyz" >}}',
      '<section data-href-uuid="abcwxyz" data-uuid="asdfasdfasdfasdf"></section>'
    )
  })
})
