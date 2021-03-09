import { ComponentType } from "react"

import MarkdownEditor from "../components/MarkdownEditor"

import { ConfigField, WebsiteContent } from "../types/websites"

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
