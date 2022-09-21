import * as Sentry from "@sentry/react"
import { isEqual } from "lodash"
const domParser = new DOMParser()

const gatherDocumentStats = (doc: Document) => {
  const tables = doc.querySelectorAll("table")
  return {
    tables: tables.length
  }
}

const validateHtml2md = (
  md: string,
  html: string,
  md2html: (md: string) => string
): void => {
  const htmlDoc = domParser.parseFromString(html, "text/html")
  const mdDoc = domParser.parseFromString(md2html(md), "text/html")
  const htmlStats = gatherDocumentStats(htmlDoc)
  const mdStats = gatherDocumentStats(mdDoc)
  if (isEqual(htmlStats, mdStats)) return
  Sentry.addBreadcrumb({
    level: "fatal",
    data:  { md, html, htmlStats, mdStats }
  })
  throw new Error("Markdown conversion error.")
}

export { validateHtml2md }
