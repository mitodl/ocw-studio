import HtmlDataProcessor from "@ckeditor/ckeditor5-engine/src/dataprocessor/htmldataprocessor"
import { Converter } from "showdown"
import GFMDataProcessor from "@ckeditor/ckeditor5-markdown-gfm/src/gfmdataprocessor"
import { editor } from "@ckeditor/ckeditor5-core"

import MarkdownConfigPlugin from "./MarkdownConfigPlugin"

import { turndownService } from "../turndown"

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
  md2html: (s: string) => string
  html2md: (s: string) => string

  constructor(
    document: DocumentFragment,
    md2html: (s: string) => string,
    html2md: (s: string) => string
  ) {
    super(document)

    this.md2html = md2html
    this.html2md = html2md
  }

  /**
   * Convert markdown string to CKEditor View
   */
  toView(md: string): DocumentFragment {
    const html = this.md2html(md)
    return this._htmlDP.toView(html)
  }

  /**
   * Convert CKEditor View to Markdown string
   */
  toData(viewFragment: DocumentFragment): string {
    const html = this._htmlDP.toData(viewFragment)
    console.log(html);
    return this.html2md(html)
  }
}

/**
 * Plugin implementing Markdown for CKEditor
 *
 * This plugin sets up the editor to use Markdown as source and output data.
 *
 * based on https://github.com/ckeditor/ckeditor5/blob/master/packages/ckeditor5-markdown-gfm/src/markdown.js
 */
export default class Markdown extends MarkdownConfigPlugin {
  constructor(editor: editor.Editor) {
    super(editor)

    const { showdownExtensions, turndownRules } = this.getMarkdownConfig()

    const converter = new Converter({
      extensions: showdownExtensions
    })

    // @ts-ignore
    if (!turndownService._customRulesSet) {
      turndownRules.forEach(({ name, rule }) =>
        turndownService.addRule(name, rule)
      )
      // @ts-ignore
      turndownService._customRulesSet = true
    }

    function md2html(md: string): string {
      return converter.makeHtml(md)
    }

    function html2md(html: string): string {
      return turndownService.turndown(html)
    }

    // some typescript wrangling necessary here unfortunately b/c of some
    // shortcomings in the typings for @ckeditor/ckeditor5-engine
    // and @ckeditor/ckeditor5-core
    (editor.data.processor as unknown) = new MarkdownDataProcessor(
      (editor.data as any).viewDocument,
      md2html,
      html2md
    )
  }

  static get pluginName(): string {
    return "Markdown"
  }
}
