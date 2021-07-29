import ClassicEditorBase from "@ckeditor/ckeditor5-editor-classic/src/classiceditor"
import { editor } from "@ckeditor/ckeditor5-core"
import { html_beautify as htmlBeautify } from "js-beautify"
import { MarkdownDataProcessor } from "./Markdown"

class ClassicTestEditor extends ClassicEditorBase {}

export const createTestEditor = (plugins: any[]) => async (
  initialData = ""
): Promise<editor.Editor> => {
  const editor = await ClassicTestEditor.create(initialData, {
    plugins
  })
  return editor
}

export function markdownTest(
  editor: editor.Editor,
  markdown: string,
  html: string
): void {
  // grab showdown and turndown functions defined by Markdown plugin
  // and passed to the MarkdownDataProcessor
  const { md2html, html2md } = editor.data.processor as MarkdownDataProcessor

  // should run both conversions without error
  md2html(markdown)
  html2md(html)

  // md2html should give html
  expect(htmlBeautify(md2html(markdown))).toBe(htmlBeautify(html))

  // html2md should give markdown
  expect(html2md(html)).toBe(markdown)

  // should be able to losslessly convert in both directions
  // html -> markdown -> html
  expect(htmlBeautify(md2html(html2md(html)))).toBe(htmlBeautify(html))
  // markdown -> html -> markdown
  expect(html2md(md2html(markdown))).toBe(markdown)
}
