import ClassicEditorBase from "@ckeditor/ckeditor5-editor-classic/src/classiceditor"
import { Editor } from "@ckeditor/ckeditor5-core"
import { html_beautify as htmlBeautify } from "js-beautify"
import { MarkdownDataProcessor } from "./Markdown"

class ClassicTestEditor extends ClassicEditorBase {}

export const createTestEditor =
  (plugins: unknown[], remainingConfig: Record<string, unknown> = {}) =>
    async (
      initialData = "",
      configOverrides: Record<string, unknown> = {}
    ): Promise<Editor & { getData(): string }> => {
      const editor = await ClassicTestEditor.create(initialData, {
        plugins,
        ...remainingConfig,
        ...configOverrides
      })
      return editor
    }

export function getConverters(editor: Editor) {
  const { md2html, html2md } = editor.data
    .processor as unknown as MarkdownDataProcessor

  return { md2html, html2md }
}

export function markdownTest(
  editor: Editor,
  markdown: string,
  html: string,
  finalMarkdown?: string
): void {
  // grab showdown and turndown functions defined by Markdown plugin
  // and passed to the MarkdownDataProcessor
  const { md2html, html2md } = editor.data
    .processor as unknown as MarkdownDataProcessor

  const outputMarkdown = finalMarkdown ?? markdown

  // should run both conversions without error
  md2html(markdown)
  html2md(html)

  // md2html should give html
  expect(htmlBeautify(md2html(markdown))).toBe(htmlBeautify(html))

  // html2md should give markdown
  expect(html2md(html)).toBe(outputMarkdown)

  // should be able to losslessly convert in both directions
  // html -> markdown -> html
  expect(htmlBeautify(md2html(html2md(html)))).toBe(htmlBeautify(html))
  // markdown -> html -> markdown
  expect(html2md(md2html(markdown))).toBe(outputMarkdown)
}

export function htmlConvertContainsTest(
  editor: Editor,
  markdown: string,
  html: string
): void {
  const { md2html, html2md } = getConverters(editor)

  expect(md2html(markdown)).toBe(html)
  expect(html2md(html)).toBe(markdown)
}
