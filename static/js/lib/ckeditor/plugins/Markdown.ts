import HtmlDataProcessor from "@ckeditor/ckeditor5-engine/src/dataprocessor/htmldataprocessor"
import { Converter } from "showdown"
import GFMDataProcessor from "@ckeditor/ckeditor5-markdown-gfm/src/gfmdataprocessor"
import { Editor } from "@ckeditor/ckeditor5-core"

import MarkdownConfigPlugin from "./MarkdownConfigPlugin"
import { ATTRIBUTE_REGEX } from "./constants"

import {
  resetTurndownService,
  turndownService,
  turndownHtmlHelpers
} from "../turndown"
import Turndown from "turndown"
import { buildAttrsString } from "./util"
import { validateHtml2md } from "./validateMdConversion"

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
    return this.html2md(html)
  }
}

const TD_CONTENT_REGEX = /<td.*?>([\S\s]*?)<\/td>/g
const TH_CONTENT_REGEX = /<th(?!ead).*?>([\S\s]*?)<\/th>/g

/**
 * Plugin implementing Markdown for CKEditor
 *
 * This plugin sets up the editor to use Markdown as source and output data.
 *
 * based on https://github.com/ckeditor/ckeditor5/blob/master/packages/ckeditor5-markdown-gfm/src/markdown.js
 */
export default class Markdown extends MarkdownConfigPlugin {
  turndownRules: Turndown.Rule[]

  allowedHtml: (keyof HTMLElementTagNameMap)[]

  constructor(editor: Editor) {
    super(editor)

    const { showdownExtensions, turndownRules, allowedHtml } =
      this.getMarkdownConfig()

    const converter = new Converter({
      extensions: showdownExtensions
    })

    converter.setFlavor("github")

    resetTurndownService()
    turndownRules.forEach(({ name, rule }) =>
      turndownService.addRule(name, rule)
    )
    this.turndownRules = [...turndownService.rules.array]
    this.allowedHtml = allowedHtml

    function formatTableCell(
      el: string,
      html: string,
      contents: string
    ): string {
      const attrs = html.match(ATTRIBUTE_REGEX)
      return `<${el}${buildAttrsString(attrs)}>${converter.makeHtml(
        contents
      )}</${el}>`
    }

    const unvalidatedMd2html = (md: string): string => {
      return converter
        .makeHtml(md)
        .replace(TD_CONTENT_REGEX, (_match, contents) =>
          formatTableCell("td", _match, contents)
        )
        .replace(TH_CONTENT_REGEX, (_match, contents) =>
          formatTableCell("th", _match, contents)
        )
    }

    const unvalidatedHtml2md = this.turndown

    const md2html = unvalidatedMd2html
    const html2md = (html: string): string => {
      const md = unvalidatedHtml2md(html)
      validateHtml2md(md, html, unvalidatedMd2html)
      return md
    }

    // some typescript wrangling necessary here unfortunately b/c of some
    // shortcomings in the typings for @ckeditor/ckeditor5-engine
    // and @ckeditor/ckeditor5-core
    editor.data.processor = new MarkdownDataProcessor(
      (editor.data as any).viewDocument,
      md2html,
      html2md
    ) as typeof HtmlDataProcessor
  }

  /**
   * The @ckeditor/ckeditor5-markdown-gfm package uses a single turndownService
   * instance for all instances of GFMDataProcessor. So sad.
   *
   * This is frustrating because we want different editors to support different
   * markdown syntaxes (e.g., "minimal" editors do not support table editing.)
   *
   * So we'll emulate separate instances by swapping out the rulesset on the
   * single instance.
   */
  turndown = (html: string) => {
    try {
      turndownService.rules.array = this.turndownRules

      turndownService.rules.keepReplacement = turndownHtmlHelpers.keepReplacer
      turndownService.keep(this.allowedHtml)

      return turndownHtmlHelpers.turndown(html)
    } finally {
      resetTurndownService()
    }
  }

  static get pluginName(): string {
    return "Markdown"
  }
}
