import HtmlDataProcessor from "@ckeditor/ckeditor5-engine/src/dataprocessor/htmldataprocessor"
import Plugin from "@ckeditor/ckeditor5-core/src/plugin"
import GFMDataProcessor from "@ckeditor/ckeditor5-markdown-gfm/src/gfmdataprocessor"

import { md2html, html2md } from "../../markdown"
import { editor } from "@ckeditor/ckeditor5-core"

/**
 * Data processor for CKEditor which implements conversion to / from Markdown
 *
 * The data processor (editor.data.processor) handles serializing and
 * deserializing data to the internal representation that CKEditor uses. This
 * data processor specifically provides support for using Markdown as the input
 * / output format.
 *
 * Markdown serialization / deserialization is implemented with our custom
 * md2html and html2md functions.  We then rely on CKEditor's HtmlDataProcessor
 * for the 'last mile' part of the conversion.
 *
 * To load markdown (toView) we convert markdown to html and  then run it
 * through the HtmlDataProcessor (_htmlDP) to convert it into data suitable to
 * load into the editor.
 *
 * To save markdown (toData) we likewise first use the HtmlDataProcessor
 * (_htmlDP) to get the data out as HTML, which we then convert to Markdown
 * using html2md.
 *
 * based on
 * https://github.com/ckeditor/ckeditor5/blob/master/packages/ckeditor5-markdown-gfm/src/gfmdataprocessor.js
 */
export class MarkdownDataProcessor extends GFMDataProcessor {
  _htmlDP: typeof HtmlDataProcessor

  constructor(document: DocumentFragment) {
    super(document)
  }

  /**
   * Convert markdown string to CKEditor View
   */
  toView(md: string): DocumentFragment {
    const html = md2html(md)
    return this._htmlDP.toView(html)
  }

  /**
   * Convert CKEditor View to Markdown string
   */
  toData(viewFragment: DocumentFragment): string {
    const html = this._htmlDP.toData(viewFragment)
    return html2md(html)
  }
}

/**
 * Plugin implementing Markdown for CKEditor
 *
 * This plugin sets up the editor to use Markdown as source and output data.
 *
 * based on https://github.com/ckeditor/ckeditor5/blob/master/packages/ckeditor5-markdown-gfm/src/markdown.js
 */
export default class Markdown extends Plugin {
  constructor(editor: editor.Editor) {
    super(editor)
    // some typescript wrangling necessary here unfortunately b/c of some
    // shortcomings in the typings for @ckeditor/ckeditor5-engine
    // and @ckeditor/ckeditor5-core
    ;(editor.data
      .processor as MarkdownDataProcessor) = new MarkdownDataProcessor(
        (editor.data as any).viewDocument
      )
  }

  static get pluginName(): string {
    return "Markdown"
  }
}
