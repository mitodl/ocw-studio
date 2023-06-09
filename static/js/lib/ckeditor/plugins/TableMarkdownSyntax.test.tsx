jest.mock("@ckeditor/ckeditor5-utils/src/version")

import { equals } from "ramda"
import Markdown from "./Markdown"
import { createTestEditor, markdownTest } from "./test_util"
import { html_beautify as htmlBeautify } from "js-beautify"
import { MarkdownDataProcessor } from "./Markdown"
import { turndownService } from "../turndown"
import ParagraphPlugin from "@ckeditor/ckeditor5-paragraph/src/paragraph"

import TableMarkdownSyntax from "./TableMarkdownSyntax"
import { TABLE_ELS } from "./constants"

const getEditor = createTestEditor([
  ParagraphPlugin,
  TableMarkdownSyntax,
  Markdown
])

describe("table shortcodes", () => {
  afterEach(() => {
    turndownService.rules.array = turndownService.rules.array.filter(
      (rule: any) => !equals(rule.filter, TABLE_ELS)
    )
  })

  it("should transform a table with rows, content", async () => {
    const editor = await getEditor("")
    markdownTest(
      editor,
      "{{< tableopen >}}{{< tbodyopen >}}{{< tropen >}}{{< tdopen >}}\n\nmy *row*\n\n{{< tdclose >}}{{< trclose >}}{{< tbodyclose >}}{{< tableclose >}}",
      `<table>
        <tbody>
          <tr>
            <td><p>my <em>row</em></p></td>
          </tr>
        </tbody>
      </table>`
    )
  })

  it("should transform a table which has lists and so on in it", async () => {
    const editor = await getEditor("")
    markdownTest(
      editor,
      "{{< tableopen >}}{{< tbodyopen >}}{{< tropen >}}{{< tdopen >}}\n\n- foo\n- *bar*\n\n{{< tdclose >}}{{< tdopen >}}\n\n# Heading\n\n{{< tdclose >}}{{< trclose >}}{{< tbodyclose >}}{{< tableclose >}}",
      `<table>
        <tbody>
          <tr>
            <td>
              <ul>
                <li>foo</li>
                <li><em>bar</em></li>
              </ul>
            </td>
            <td><h1 id="heading">Heading</h1></td>
          </tr>
        </tbody>
      </table>`
    )
  })

  it("should transform a table with a header", async () => {
    const editor = await getEditor("")
    markdownTest(
      editor,
      "{{< tableopen >}}{{< theadopen >}}{{< tropen >}}{{< thopen >}}\n\nA **column**\n\n{{< thclose >}}{{< thopen >}}\n\nAnother column\n\n{{< thclose >}}{{< trclose >}}{{< theadclose >}}{{< tbodyopen >}}{{< tropen >}}{{< tdopen >}}\n\ndata\n\n{{< tdclose >}}{{< tdopen >}}\n\ndata\n\n{{< tdclose >}}{{< trclose >}}{{< tbodyclose >}}{{< tableclose >}}",
      `<table>
        <thead>
          <tr>
            <th><p>A <strong>column</strong></p></th>
            <th><p>Another column</p></th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><p>data</p></td>
            <td><p>data</p></td>
          </tr>
        </tbody>
      </table>`
    )
  })

  it("should transform a table with colspan and rowspan attributes", async () => {
    const editor = await getEditor("")
    markdownTest(
      editor,
      `{{< tableopen >}}{{< theadopen >}}{{< tropen >}}{{< thopen colspan="2" >}}\n\n**A title row**\n\n{{< thclose >}}{{< trclose >}}{{< theadclose >}}{{< tbodyopen >}}{{< tropen >}}{{< tdopen rowspan="2" >}}\n\nrowspan test\n\n{{< tdclose >}}{{< tdopen >}}\n\nrowspan 1\n\n{{< tdclose >}}{{< trclose >}}{{< tropen >}}{{< tdopen >}}\n\nrowspan 2\n\n{{< tdclose >}}{{< trclose >}}{{< tbodyclose >}}{{< tableclose >}}`,
      `<table>
        <thead>
          <tr>
            <th colspan="2">
              <p><strong>A title row</strong></p>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td rowspan="2">
              <p>rowspan test</p>
            </td>
            <td>
              <p>rowspan 1</p>
            </td>
          </tr>
          <tr>
            <td>
              <p>rowspan 2</p>
            </td>
          </tr>
        </tbody>
      </table>`
    )
  })

  it("ignores attributes on table cells that are not in the whitelist", async () => {
    const editor = await getEditor("")
    const { md2html, html2md } = editor.data
      .processor as unknown as MarkdownDataProcessor
    let html = `<table>
      <thead>
        <tr>
          <th colspan="2">
            <p><strong>A title row</strong></p>
          </th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td class="sneaky-css-class"><p>data</p></td>
          <td><p>data</p></td>
        </tr>
      </tbody>
    </table>`
    let md = `{{< tableopen >}}{{< theadopen >}}{{< tropen >}}{{< thopen colspan="2" >}}\n\n**A title row**\n\n{{< thclose >}}{{< trclose >}}{{< theadclose >}}{{< tbodyopen >}}{{< tropen >}}{{< tdopen >}}\n\ndata\n\n{{< tdclose >}}{{< tdopen >}}\n\ndata\n\n{{< tdclose >}}{{< trclose >}}{{< tbodyclose >}}{{< tableclose >}}`
    expect(html2md(html)).toBe(md)
    md = `{{< tableopen >}}{{< theadopen >}}{{< tropen >}}{{< thopen colspan="2" >}}\n\n**A title row**\n\n{{< thclose >}}{{< trclose >}}{{< theadclose >}}{{< tbodyopen >}}{{< tropen >}}{{< tdopen class="sneaky-css-class" >}}\n\ndata\n\n{{< tdclose >}}{{< tdopen >}}\n\ndata\n\n{{< tdclose >}}{{< trclose >}}{{< tbodyclose >}}{{< tableclose >}}`
    html = `<table>
      <thead>
        <tr>
          <th colspan="2">
            <p><strong>A title row</strong></p>
          </th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><p>data</p></td>
          <td><p>data</p></td>
        </tr>
      </tbody>
    </table>`
    expect(htmlBeautify(md2html(md))).toBe(htmlBeautify(html))
  })

  it.each([
    [
      "<table><thead><tr><th>my content</th></tr></thead></table>",
      "{{< tableopen >}}{{< theadopen >}}{{< tropen >}}{{< thopen >}}\nmy content\n{{< thclose >}}{{< trclose >}}{{< theadclose >}}{{< tableclose >}}"
    ],
    [
      "<table><tbody><tr><td>more content</td></tr></tbody></table>",
      "{{< tableopen >}}{{< tbodyopen >}}{{< tropen >}}{{< tdopen >}}\nmore content\n{{< tdclose >}}{{< trclose >}}{{< tbodyclose >}}{{< tableclose >}}"
    ]
  ])(
    "html2md should add newlines on table cell content when appropriate",
    async (html, md) => {
      const editor = await getEditor("")
      const { html2md } = editor.data
        .processor as unknown as MarkdownDataProcessor
      expect(html2md(html)).toBe(md)
    }
  )
})
