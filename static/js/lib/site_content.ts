import { ComponentType, ElementType } from "react"
import { pick } from "ramda"

import MarkdownEditor from "../components/widgets/MarkdownEditor"
import FileUploadField from "../components/widgets/FileUploadField"
import SelectField from "../components/widgets/SelectField"
import BooleanField from "../components/widgets/BooleanField"

import { objectToFormData } from "./util"
import {
  MAIN_PAGE_CONTENT_DB_FIELD,
  MAIN_PAGE_CONTENT_FIELD
} from "../constants"

import { ConfigField, WebsiteContent, WidgetVariant } from "../types/websites"

export const componentFromWidget = (
  field: ConfigField
): string | ComponentType | ElementType | null => {
  switch (field.widget) {
  case WidgetVariant.Markdown:
    return MarkdownEditor
  case WidgetVariant.Select:
    return SelectField
  case WidgetVariant.File:
    return FileUploadField
  case WidgetVariant.Boolean:
    return BooleanField
  case WidgetVariant.Text:
    return "textarea"
  case WidgetVariant.Hidden:
    return null
  default:
    return "input"
  }
}

const SELECT_EXTRA_PROPS = ["options", "multiple", "max", "min"]

export function widgetExtraProps(field: ConfigField): Record<string, any> {
  switch (field.widget) {
  case WidgetVariant.Select:
    return pick(SELECT_EXTRA_PROPS, field)
  case WidgetVariant.Markdown:
    return { minimal: field.minimal ?? false }
  default:
    return {}
  }
}

const isMainContentField = (field: ConfigField) =>
  field.name === MAIN_PAGE_CONTENT_FIELD &&
  field.widget === WidgetVariant.Markdown

type ValueType = string | File | string[] | null
const emptyValue = (field: ConfigField): ValueType => {
  switch (field.widget) {
  case "select":
    if (field.multiple) {
      return []
    } else {
      return null
    }
  case "file":
    return null
  default:
    return ""
  }
}

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
    let value = values[field.name]
    if (!fieldHasData(field, values)) {
      value = emptyValue(field)
    }

    if (value !== undefined) {
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
      values[field.name] = metadata[field.name] ?? defaultFor(field.widget)
    }
  }
  return values
}

export const newInitialValues = (fields: ConfigField[]): Record<string, any> =>
  Object.fromEntries(
    fields.map((field: ConfigField) => [
      field.name,
      field.default ?? defaultFor(field.widget)
    ])
  )

const defaultFor = (widget: WidgetVariant): string | boolean =>
  widget === WidgetVariant.Boolean ? false : ""

/**
 * Should field data be sent to the server?
 */
export function fieldHasData(
  field: ConfigField,
  values: Record<string, ValueType>
): boolean {
  if (!field.condition) {
    return true
  }

  const condition = field.condition
  return values[condition.field] === condition.equals
}

/**
 * Should field, label, and validation be displayed in the UI?
 */
export const fieldIsVisible = (
  field: ConfigField,
  values: Record<string, ValueType>
): boolean => field.widget !== "hidden" && fieldHasData(field, values)
