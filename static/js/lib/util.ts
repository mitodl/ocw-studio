import { isEmpty } from "ramda"
import { ActionPromiseValue } from "redux-query"
import { ComponentType } from "react"

import { ConfigField, WebsiteContent } from "../types/websites"
import MarkdownEditor from "../components/MarkdownEditor"

export const isErrorStatusCode = (statusCode: number): boolean =>
  statusCode >= 400

export const isErrorResponse = (response: ActionPromiseValue<any>): boolean =>
  isErrorStatusCode(response.status)

/*
 * If an HTTP response contains errors in the body, return either a string representing
 */
export const getResponseBodyError = (
  response: ActionPromiseValue<any>
): string | { [key: string]: string } | null => {
  if (!response || !response.body) {
    return null
  }
  // Errors may be namespaced under an "errors" key, or just at the top level of the response body
  const errors = response.body.errors || response.body
  if (isEmpty(errors)) {
    return null
  }
  if (Array.isArray(errors)) {
    // Just return the first error message if a list was returned
    return errors.length === 0 ? null : errors[0]
  }
  return errors
}

export const componentFromWidget = (
  field: ConfigField
): string | ComponentType => {
  switch (field.widget) {
  case "markdown":
    return MarkdownEditor
  default:
    return "input"
  }
}

export const contentFormValuesToPayload = (
  values: { [key: string]: string },
  fields: ConfigField[]
): Record<string, string> & { metadata?: Record<string, string> } => {
  const payload = {}
  const metadata: { [key: string]: string } = {}

  if (values["type"]) {
    payload["type"] = values["type"]
  }

  for (const field of fields) {
    const value = values[field.name]
    if (value !== null && value !== undefined) {
      if (field.widget === "markdown") {
        payload["markdown"] = value
      } else if (field.name === "title") {
        payload[field.name] = value
      } else {
        metadata[field.name] = value
      }
    }
  }

  if (Object.keys(metadata).length > 0) {
    payload["metadata"] = metadata
  }
  return payload
}

export const contentInitialValues = (
  content: WebsiteContent,
  fields: ConfigField[]
): { [key: string]: string } => {
  const values = {}
  const metadata = content.metadata ?? {}

  for (const field of fields) {
    if (field.widget === "markdown") {
      values[field.name] = content.markdown ?? ""
    } else if (field.name === "title") {
      values[field.name] = content[field.name] ?? ""
    } else {
      values[field.name] = metadata[field.name] ?? ""
    }
  }
  return values
}
