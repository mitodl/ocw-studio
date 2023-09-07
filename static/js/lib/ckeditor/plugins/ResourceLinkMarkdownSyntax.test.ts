jest.mock("@ckeditor/ckeditor5-utils/src/version")
jest.mock("@ckeditor/ckeditor5-link/src/linkui")

import LinkPlugin from "@ckeditor/ckeditor5-link/src/link"

import Markdown from "./Markdown"
import { createTestEditor, markdownTest, getConverters } from "./test_util"
import { turndownService } from "../turndown"

import { RESOURCE_LINK, RESOURCE_LINK_CONFIG_KEY } from "./constants"
import ResourceLinkMarkdownSyntax from "./ResourceLinkMarkdownSyntax"
import Paragraph from "@ckeditor/ckeditor5-paragraph/src/paragraph"
import LegacyShortcodes from "./LegacyShortcodes"

const getEditor = createTestEditor(
  [
    Paragraph,
    LinkPlugin,
    ResourceLinkMarkdownSyntax,
    LegacyShortcodes,
    Markdown,
  ],
  {
    [RESOURCE_LINK_CONFIG_KEY]: {
      hrefTemplate: "https://fake.mit.edu/:uuid",
    },
  },
)
const href = (uuid: string, suffix = "") =>
  `https://fake.mit.edu/${uuid}?ocw_resource_link_uuid=${uuid}&ocw_resource_link_suffix=${suffix}`

describe("ResourceLinkMarkdownSyntax plugin", () => {
  afterEach(() => {
    turndownService.rules.array = turndownService.rules.array.filter(
      (rule: any) => rule.name !== RESOURCE_LINK,
    )
  })

  it("should take in and return 'resource_link' shortcode", async () => {
    const md = '{{% resource_link "1234567890" "link text" %}}'
    const editor = await getEditor(md)

    expect(editor.getData()).toBe(md)
  })

  it("should serialize to and from markdown (with fragment)", async () => {
    const md =
      '{{% resource_link "1234-5678" "link text" "some-header-id" %}}{{% resource_link "link-this-here-uuid" "Title of the Link" "some-heading-id" %}}'
    const editor = await getEditor(md)
    expect(editor.getData()).toBe(md)

    markdownTest(
      editor,
      '{{% resource_link "1234-5678" "link text" "#some-header-id" %}}',
      `<p><a href="${href(
        "1234-5678",
        "%23some-header-id",
      )}">link text</a></p>`,
    )
  })

  it("should serialize to and from markdown (without fragment)", async () => {
    const editor = await getEditor("")
    markdownTest(
      editor,
      '{{% resource_link "asdfasdfasdfasdf" "text here" %}}',
      `<p><a href="${href("asdfasdfasdfasdf")}">text here</a></p>`,
    )
  })

  it("displays quotes properly", async () => {
    const editor = await getEditor("")
    const text = 'not "escaped" in the html'
    markdownTest(
      editor,
      '{{% resource_link "asdfasdfasdfasdf" "not \\"escaped\\" in the html" %}}',
      `<p><a href="${href("asdfasdfasdfasdf")}">${text}</a></p>`,
    )
  })

  it("should serialize multiple links to and from markdown", async () => {
    const editor = await getEditor("")
    markdownTest(
      editor,
      'dogs {{% resource_link "uuid1" "woof" %}} cats {{% resource_link "uuid2" "meow" %}}, cool',
      `<p>dogs <a href="${href("uuid1")}">woof</a> cats <a href="${href(
        "uuid2",
      )}">meow</a>, cool</p>`,
    )
  })

  it.each([
    'Dogs {{% resource_link uuid123 "bark bark" %}} Woof',
    'Dogs {{% resource_link "uuid123" "bark bark" %}} Woof',
  ])("tolerates quotation marks around its argument", async (md) => {
    const editor = await getEditor("")
    // This conversion is not quite lossless. We lose the optional quotes around
    // shortcode argument.
    const { md2html } = getConverters(editor)
    expect(md2html(md)).toBe(
      `<p>Dogs <a href="${href("uuid123")}">bark bark</a> Woof</p>`,
    )
  })

  it("Treats legacy shortcodes in link text as literal text", async () => {
    const editor = await getEditor("")
    const md = 'Dogs {{% resource_link "uuid123" "{{< sup 2 >}}" %}} Woof'
    const html = `<p>Dogs <a href="${href(
      "uuid123",
    )}">{{&lt; sup 2 &gt;}}</a> Woof</p>`
    markdownTest(editor, md, html)
  })

  it.each([
    {
      allowedHtml: ["sup"],
      sup: (x: string) => `<sup>${x}</sup>`,
    },
    {
      allowedHtml: [""],
      sup: (x: string) => x,
    },
  ])(
    "Preserves superscripts in the link title iff sub tag is permitted",
    async ({ allowedHtml, sup }) => {
      const editor = await getEditor("", {
        "markdown-config": { allowedHtml },
      })
      const { md2html, html2md } = getConverters(editor)

      const html = `<p>Dogs <sup>x</sup> <a href="${href(
        "uuid123",
      )}">Einstein says E=mc<sup>2</sup></a> Woof</p>`

      const md =
        'Dogs <sup>x</sup> {{% resource_link "uuid123" "Einstein says E=mc<sup>2</sup>" %}} Woof'
      /**
       * md -> html always keeps extra tags
       */
      expect(md2html(md)).toBe(html)

      /**
       * html -> md only keeps extra tags if specified by allowedHtml
       */
      expect(html2md(html)).toBe(
        `Dogs ${sup("x")} {{% resource_link "uuid123" "Einstein says E=mc${sup(
          "2",
        )}" %}} Woof`,
      )
    },
  )

  /**
   * It seems that this scenario cannot actually be constructed in CKEditor.
   * CKEditor treats subscripts, subscripts, links, and resource links as
   * attributes on a text node, not as some sort of tree structure (like html)
   * with nesting. It's unclear how the conversion order from "attributes on
   * text node" to an HTML tree is performed, but it seems that resource_link
   * always ends up on the outside.
   *
   * Still, nice that this works.
   */
  it("Preserves resource links inside superscripts if sup enabled", async () => {
    const editor = await getEditor("", {
      "markdown-config": { allowedHtml: ["sup"] },
    })
    const md =
      'Cool reference<sup>{{% resource_link "uuid123" "\\[1\\]" %}}</sup>'
    const html = `<p>Cool reference<sup><a href="${href(
      "uuid123",
    )}">[1]</a></sup></p>`

    markdownTest(editor, md, html)
  })
})
