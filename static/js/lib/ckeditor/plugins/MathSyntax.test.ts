/* eslint-disable prefer-template */
import { editor } from "@ckeditor/ckeditor5-core"
import Markdown from "./Markdown"
import { createTestEditor, getConverters, htmlConvertContainsTest } from "./test_util"
import MathSyntax from "./MathSyntax"

const getEditor = createTestEditor([MathSyntax, Markdown])

const display = { name: "display", start: "\\\\[", end: "\\\\]", scriptType: "math/tex; mode=display" }
const inline = { name: "display", start: "\\\\[", end: "\\\\]", scriptType: "math/tex; mode=display" }
const modes = [display, inline]

const scriptify = (mode: { scriptType: string }, math: string): string =>  `<script type="${mode.scriptType}">${math}</script>`

describe.each(modes)("MathSyntax converstion to/from $mode", mode => {
  test.each([
    {
      at:   "start",
      html: (m: string) => `<p>${m} and then MIDDLE text and the END</p>`,
      md:   (m: string) => `${m} and then MIDDLE text and the END`
    },
    {
      at:   "middle",
      html: (m: string) => `<p>START and then ${m} text and the END</p>`,
      md:   (m: string) => `START and then ${m} text and the END`
    },
    {
      at:   "end",
      html: (m: string) => `<p>START and then MIDDLE text and the ${m}</p>`,
      md:   (m: string) => `START and then MIDDLE text and the ${m}`
    }
  ])("converts math to/from markdown at the $at of text", async get => {
    const editor = await getEditor()
    const math = "x^2 + y^2 = z^2"
    const md = get.md(mode.start + math + mode.end)
    const html = get.html(scriptify(mode, math))
    await htmlConvertContainsTest(editor, md, html)
  })

  test.each([
    "1 + 1 < 3",
    "1 + 1 > 0"
  ])("It converts '%p' correctly", async math => {
    const editor = await getEditor()
    const md = mode.start + math + mode.end
    const html = `<p>${scriptify(mode, math)}</p>`
    await htmlConvertContainsTest(editor, md, html)
  })
})

test("Display math with new lines", async () => {
  const editor = await getEditor()
  const { md2html, html2md } = getConverters(editor)
  const math = String.raw`\begin{align} 1 + 1 = & 2 \\\\ x + y = & z \end{align}`
  const md = String.raw`\\[${math}\\]`
  const html = `<p>${scriptify(
    display,
    String.raw`\begin{align} 1 + 1 = & 2 \\ x + y = & z \end{align}`
  )}</p>`

  expect(html2md(md2html(md))).toBe(md)
  expect(md2html(html2md(html))).toBe(html)
})
