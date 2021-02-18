import { Converter } from "showdown"
import { turndownService } from "@ckeditor/ckeditor5-markdown-gfm/src/html2markdown/html2markdown"

export function html2md(html: string): string {
  return turndownService.turndown(html)
}

const converter = new Converter()

export function md2html(md: string): string {
  return converter.makeHtml(md)
}
