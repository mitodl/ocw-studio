import HtmlDataProcessor from "@ckeditor/ckeditor5-engine/src/dataprocessor/htmldataprocessor"
import Plugin from "@ckeditor/ckeditor5-core/src/plugin"
import GFMDataProcessor from "@ckeditor/ckeditor5-markdown-gfm/src/gfmdataprocessor"

import { md2html, html2md } from "../../markdown"

/**
 * Data processor for CKEDitor which implements conversion to / from Markdown
 *
 * based on https://github.com/ckeditor/ckeditor5/blob/master/packages/ckeditor5-markdown-gfm/src/gfmdataprocessor.js
 */
export class MarkdownDataProcessor extends GFMDataProcessor {
  _htmlDP: typeof HtmlDataProcessor

  constructor(document: DocumentFragment) {
    super(document)
  }

  /**
   * Convert markdown string to ckeditor view state
   */
  toView(md: string): DocumentFragment {
    const html = md2html(md)
    return this._htmlDP.toView(html)
  }

  /**
   * Convert ckeditor view state to markdown string
   */
  toData(viewFragment: DocumentFragment): string {
    const html = this._htmlDP.toData(viewFragment)
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
  constructor(editor: any) {
    super(editor)
    editor.data.processor = new MarkdownDataProcessor(editor.data.viewDocument)
  }

  static get pluginName() {
    return "Markdown"
  }
}
