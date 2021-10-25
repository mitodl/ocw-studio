jest.mock("@ckeditor/ckeditor5-utils/src/version")

import { equals } from "ramda"
import Markdown from "./Markdown"
import { createTestEditor, markdownTest } from "./test_util"
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
    // @ts-ignore
    turndownService._customRulesSet = undefined
  })

  it("should transform a table with rows, content", async () => {
    const editor = await getEditor("")
    markdownTest(
      editor,
      "{{< tableopen >}}{{< tbodyopen >}}{{< tropen >}}{{< tdopen >}}\nmy _row_\n{{< tdclose >}}{{< trclose >}}{{< tbodyclose >}}{{< tableclose >}}",
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
      "{{< tableopen >}}{{< tbodyopen >}}{{< tropen >}}{{< tdopen >}}\n- foo\n- _bar_\n{{< tdclose >}}{{< tdopen >}}\n# Heading\n{{< tdclose >}}{{< trclose >}}{{< tbodyclose >}}{{< tableclose >}}",
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
      "{{< tableopen >}}{{< theadopen >}}{{< tropen >}}{{< thopen >}}\nA **column**\n{{< thclose >}}{{< thopen >}}\nAnother column\n{{< thclose >}}{{< trclose >}}{{< theadclose >}}{{< tbodyopen >}}{{< tropen >}}{{< tdopen >}}\ndata\n{{< tdclose >}}{{< tdopen >}}\ndata\n{{< tdclose >}}{{< trclose >}}{{< tbodyclose >}}{{< tableclose >}}",
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
})
