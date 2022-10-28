import { validateHtml2md } from "./validateMdConversion"
import { createTestEditor, getConverters } from "./test_util"
import Markdown from "./Markdown"
import TableMarkdownSyntax from "./TableMarkdownSyntax"

const getEditor = createTestEditor([TableMarkdownSyntax, Markdown])

const html = {
  oneTable: `
  <div>
    <table></table>
  </div>
  `,
  twoTable: `
  <div>
    <table></table>
    <table></table>
  </div>
  `
}

const md = {
  oneTable: `
  {{< tableopen >}}{{< tableclose >}}
  `,
  twoTable: `
  {{< tableopen >}}{{< tableclose >}}
  {{< tableopen >}}{{< tableclose >}}
  `
}

describe("validateHtml2md", () => {
  it("Does nothing when", async () => {
    const { md2html } = getConverters(await getEditor())
    const shouldNotError = () =>
      validateHtml2md(md.oneTable, html.oneTable, md2html)
    expect(shouldNotError).not.toThrow()
  })

  it("Errors when", async () => {
    const { md2html } = getConverters(await getEditor())
    const shouldError = () =>
      validateHtml2md(md.oneTable, html.twoTable, md2html)
    expect(shouldError).toThrow(/Markdown conversion error/)
  })
})
