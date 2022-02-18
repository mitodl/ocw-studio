jest.mock("@ckeditor/ckeditor5-utils/src/version")

import ResourceLink from "@mitodl/ckeditor5-resource-link/src/link"
import Markdown, { MarkdownDataProcessor } from "./Markdown"
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

  it("should serialize multiple links to and from markdown", async () => {
    const editor = await getEditor("")
    markdownTest(
      editor,
      'dogs {{< resource_link uuid1 "woof" >}} cats {{< resource_link uuid2 "meow" >}}, cool',
      '<p>dogs <a class="resource-link" data-uuid="uuid1">woof</a> cats <a class="resource-link" data-uuid="uuid2">meow</a>, cool</p>'
    )
  })

  it("should serialize fragment arg to and from markdown", async () => {
    const editor = await getEditor("")
    markdownTest(
      editor,
      '{{< resource_link asdfasdfasdfasdf "text here" "some-fragment-id" >}}',
      '<p><a class="resource-link" data-uuid="asdfasdfasdfasdf" data-fragment="some-fragment-id">text here</a></p>'
    )
  })

  it("[BUG] does not behave well if link title ends in backslash", async () => {
    const editor = await getEditor("")
    const { md2html } = (editor.data
      .processor as unknown) as MarkdownDataProcessor
    expect(md2html('{{< resource_link uuid123 "bad \\" >}}')).toBe(
      // This is wrong. Should not end in &lt;/a&gt;
      '<p><a class="resource-link" data-uuid="uuid123">bad &lt;/a&gt;</p>'
    )
  })
})
