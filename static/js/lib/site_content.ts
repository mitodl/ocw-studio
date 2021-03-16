import { ComponentType, ElementType } from "react"

import MarkdownEditor from "../components/MarkdownEditor"

import { ConfigField, WebsiteContent } from "../types/websites"
import FileUploadField from "../components/forms/FileUploadField"
import { objectToFormData } from "./util"

export const componentFromWidget = (
  field: ConfigField
): string | ComponentType | ElementType => {
  switch (field.widget) {
  case "markdown":
    return MarkdownEditor
  case "file":
    return FileUploadField
  default:
    return "input"
  }
}

export const contentFormValuesToPayload = (
  values: { [key: string]: string | File },
  fields: ConfigField[]
):
  | (Record<string, string> & { metadata?: Record<string, string> })
  | FormData => {
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
        // @ts-ignore
      } else if (field.name === "file" && value instanceof File) {
        payload[field.name] = value
      } else {
        metadata[field.name] = value.toString()
      }
    }
  }

  if (Object.keys(metadata).length > 0) {
    payload["metadata"] = metadata
  }

  return values["file"] ? objectToFormData(payload) : payload
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
    } else if (field.name === "file") {
      values[field.name] = content[field.name] ?? null
    } else {
      values[field.name] = metadata[field.name] ?? ""
    }
  }
  return values
}
