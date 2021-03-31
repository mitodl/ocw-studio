import { ComponentType, ElementType } from "react"

import {
  MarkdownEditor,
  MinimalMarkdownEditor
} from "../components/widgets/MarkdownEditor"
import FileUploadField from "../components/widgets/FileUploadField"
import SelectField from "../components/widgets/SelectField"

import { objectToFormData } from "./util"
import {
  MAIN_PAGE_CONTENT_DB_FIELD,
  MAIN_PAGE_CONTENT_FIELD
} from "../constants"

import { ConfigField, WebsiteContent } from "../types/websites"

export const componentFromWidget = (
  field: ConfigField
): string | ComponentType | ElementType => {
  switch (field.widget) {
  case "markdown":
    if (field.minimal) {
      return MinimalMarkdownEditor
    } else {
      return MarkdownEditor
    }
  case "select":
    return SelectField
  case "file":
    return FileUploadField
  default:
    return "input"
  }
}

const isMainContentField = (field: ConfigField) =>
  field.name === MAIN_PAGE_CONTENT_FIELD && field.widget === "markdown"

type ValueType = string | File | string[] | null
/*
 * Translates page content form values into a payload that our REST API understands.
 */
export const contentFormValuesToPayload = (
  values: Record<string, ValueType>,
  fields: ConfigField[]
):
  | (Record<string, string> & { metadata?: Record<string, string> })
  | FormData => {
  const payload = {}
  const metadata = {}

  if (values["type"]) {
    payload["type"] = values["type"]
  }

  for (const field of fields) {
    const value = values[field.name]
    if (value !== null && value !== undefined) {
      // Our API expects these bits of data as top-level keys in the payload:
      // (1) main page content in markdown, (2) title, (3) a file. None of those values are required.
      // All other values are nested under the "metadata" key.
      if (isMainContentField(field)) {
        payload[MAIN_PAGE_CONTENT_DB_FIELD] = value
      } else if (field.name === "title") {
        payload[field.name] = value
        // @ts-ignore
      } else if (field.name === "file" && value instanceof File) {
        payload[field.name] = value
      } else {
        metadata[field.name] = value
      }
    }
  }

  if (Object.keys(metadata).length > 0) {
    payload["metadata"] = metadata
  }

  return values["file"] ? objectToFormData(payload) : payload
}

/*
 * Translates site content REST API data into initial values that our forms understand.
 */
export const contentInitialValues = (
  content: WebsiteContent,
  fields: ConfigField[]
): { [key: string]: string } => {
  const values = {}
  const metadata = content.metadata ?? {}

  for (const field of fields) {
    if (isMainContentField(field)) {
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

export function newInitialValues(fields: ConfigField[]): Record<string, any> {
  const initialValues = {}
  for (const field of fields) {
    // set to empty string to treat as a controlled component
    initialValues[field.name] = field.default ?? ""
  }
  return initialValues
}
