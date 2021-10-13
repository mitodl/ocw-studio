jest.mock("@ckeditor/ckeditor5-utils/src/version")

import ResourceLink from "@mitodl/ckeditor5-resource-link/src/link"
import Markdown from "./Markdown"
import { createTestEditor, markdownTest } from "./test_util"
import { turndownService } from "../turndown"

import { RESOURCE_LINK } from "@mitodl/ckeditor5-resource-link/src/constants"
import ResourceLinkMarkdownSyntax from "./ResourceLinkMarkdownSyntax"
import Paragraph from "@ckeditor/ckeditor5-paragraph/src/paragraph"

const getEditor = createTestEditor([
  Paragraph,
  ResourceLink,
  ResourceLinkMarkdownSyntax,
  Markdown
])

jest.mock("@mitodl/ckeditor5-resource-link/src/linkui")

describe("ResourceLink plugin", () => {
  afterEach(() => {
    turndownService.rules.array = turndownService.rules.array.filter(
      (rule: any) => rule.name !== RESOURCE_LINK
    )
    // @ts-ignore
    turndownService._customRulesSet = undefined
  })

  it("should take in and return 'resource' shortcode", async () => {
    const editor = await getEditor(
      '{{< resource_link 1234567890 "link text" >}}'
    )

    // @ts-ignore
    expect(editor.getData()).toBe(
      '{{< resource_link 1234567890 "link text" >}}'
    )
  })

  it("should serialize to and from markdown", async () => {
    const editor = await getEditor("")
    markdownTest(
      editor,
      '{{< resource_link asdfasdfasdfasdf "text here" >}}',
      '<p><a class="resource-link" data-uuid="asdfasdfasdfasdf">text here</a></p>'
    )
  })
})
