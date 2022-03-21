jest.mock("@ckeditor/ckeditor5-utils/src/version")

import ResourceLink from "@mitodl/ckeditor5-resource-link/src/link"
import Markdown from "./Markdown"
import { createTestEditor, markdownTest, getConverters } from "./test_util"
import { turndownService } from "../turndown"

import { RESOURCE_LINK } from "@mitodl/ckeditor5-resource-link/src/constants"
import ResourceLinkMarkdownSyntax, {
  encodeShortcodeArgs as encode
} from "./ResourceLinkMarkdownSyntax"
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
    const md = '{{% resource_link 1234567890 "link text" %}}'
    const editor = await getEditor(md)

    // @ts-ignore
    expect(editor.getData()).toBe(md)
  })

  it("should not mash an anchor hash thingy", async () => {
    const md =
      '{{% resource_link 1234-5678 "link text" "some-header-id" %}}{{% resource_link link-this-here-uuid "Title of the Link" "some-heading-id" %}}'
    const editor = await getEditor(md)
    // @ts-ignore
    expect(editor.getData()).toBe(md)

    markdownTest(
      editor,
      '{{% resource_link 1234-5678 "link text" "#some-header-id" %}}',
      `<p><a class="resource-link" data-uuid="${encode(
        "1234-5678",
        "#some-header-id"
      )}">link text</a></p>`
    )
  })

  it("should serialize to and from markdown", async () => {
    const editor = await getEditor("")
    markdownTest(
      editor,
      '{{% resource_link asdfasdfasdfasdf "text here" %}}',
      `<p><a class="resource-link" data-uuid="${encode(
        "asdfasdfasdfasdf"
      )}">text here</a></p>`
    )
  })

  it("should serialize multiple links to and from markdown", async () => {
    const editor = await getEditor("")
    markdownTest(
      editor,
      'dogs {{% resource_link uuid1 "woof" %}} cats {{% resource_link uuid2 "meow" %}}, cool',
      `<p>dogs <a class="resource-link" data-uuid="${encode(
        "uuid1"
      )}">woof</a> cats <a class="resource-link" data-uuid="${encode(
        "uuid2"
      )}">meow</a>, cool</p>`
    )
  })

  it.each([
    'Dogs {{% resource_link uuid123 "bark bark" %}} Woof',
    'Dogs {{% resource_link "uuid123" "bark bark" %}} Woof'
  ])("tolerates quotation marks around its argument", async md => {
    const editor = await getEditor("")
    // This conversion is not quite lossless. We lose the optional quotes around
    // shortcode argument.
    const { md2html } = getConverters(editor)
    expect(md2html(md)).toBe(
      `<p>Dogs <a class="resource-link" data-uuid="${encode(
        "uuid123"
      )}">bark bark</a> Woof</p>`
    )
  })

  it("[BUG] does not behave well if link title ends in backslash", async () => {
    const editor = await getEditor("")
    const { md2html } = getConverters(editor)
    expect(md2html('{{% resource_link uuid123 "bad \\" %}}')).toBe(
      // This is wrong. Should not end in &lt;/a&gt;
      `<p><a class="resource-link" data-uuid="${encode(
        "uuid123"
      )}">bad &lt;/a&gt;</p>`
    )
  })
})
