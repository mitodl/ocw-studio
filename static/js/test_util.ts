import { FormikState } from "formik"
import { html_beautify as htmlBeautify } from "js-beautify"

import { html2md, md2html } from "./lib/markdown"

export const defaultFormikChildProps: FormikState<any> = {
  values:       {},
  errors:       {},
  touched:      {},
  isSubmitting: false,
  isValidating: false,
  status:       null,
  submitCount:  0
}

export const TEST_MARKDOWN = `## A heading

Amazing stuff! Paragraphs!

And another paragraph!

**bold** and even _ita**lic and bold** text_

- a
- list
- of
- items
- including
- [links](https://reactjs.org/docs/hooks-faq.html#how-can-i-measure-a-dom-node)
- and
    - some
    - nested
    - items!

also have some

> block quotes

good stuff.`

export function markdownTest(markdown: string, html: string): void {
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
