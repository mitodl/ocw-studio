import { DocumentFragment } from "@ckeditor/ckeditor5-engine"
import HtmlDataProcessor from "@ckeditor/ckeditor5-engine/src/dataprocessor/htmldataprocessor"
import Plugin from "@ckeditor/ckeditor5-core/src/plugin"
import { editor } from '@ckeditor/ckeditor5-core'

import { md2html, html2md } from '../../markdown'

/**
 * Data processor for CKEDitor which implements conversion to / from Markdown
 *
 * based on https://github.com/ckeditor/ckeditor5/blob/master/packages/ckeditor5-markdown-gfm/src/gfmdataprocessor.js
 */
export class MarkdownDataProcessor {
  htmlDataProcessor: dataprocessor.HtmlDataProcessor

  constructor(document: DocumentFragment) {
      this.htmlDataProcessor = new dataprocessor.HtmlDataProcessor(document)
  }

  /**
   * Convert markdown string to ckeditor view state
   * @returns {module:engine/view/documentfragment~DocumentFragment} The converted view element.
   */
  toView(md: string): DocumentFragment {
    const html = md2html(md)
    return this.htmlDataProcessor.toView(html)
  }

  /**
   * Convert ckeditor view state to markdown string
   */
  toData(viewFragment: DocumentFragment): string {
    const html = this.htmlDataProcessor.toData(viewFragment)
    return html2md(html)
  }
}

/**
 * Plugin implementing Markdown for CKEditor
 *
 * This plugin sets up the editor to use Markdown as source and output data
 *
 * based on https://github.com/ckeditor/ckeditor5/blob/master/packages/ckeditor5-markdown-gfm/src/markdown.js
 */
export default class Markdown extends Plugin {
  constructor(editor: editor.Editor) {
    super(editor)
    editor.data.processor = new MarkdownDataProcessor(editor.data.viewDocument)
  }

  static get pluginName() {
    return "Markdown"
  }
}
