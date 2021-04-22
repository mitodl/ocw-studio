import { ComponentType, ElementType } from "react"
import { pick, partition } from "ramda"

import MarkdownEditor from "../components/widgets/MarkdownEditor"
import FileUploadField from "../components/widgets/FileUploadField"
import SelectField from "../components/widgets/SelectField"
import BooleanField from "../components/widgets/BooleanField"

import { objectToFormData } from "./util"
import {
  MAIN_PAGE_CONTENT_DB_FIELD,
  MAIN_PAGE_CONTENT_FIELD
} from "../constants"

import {
  ConfigField,
  EditableConfigItem,
  TopLevelConfigItem,
  WebsiteContent,
  WidgetVariant
} from "../types/websites"
import { SiteFormValues, ValueType } from "../types/forms"

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

/**
 * determine whether a ConfigField is a main content field or not.
 * this means, basically, whether it's the main Markdown field for
 * a piece of site content.
 **/
export const isMainContentField = (field: ConfigField): boolean =>
  field.name === MAIN_PAGE_CONTENT_FIELD &&
  field.widget === WidgetVariant.Markdown

/**
 * split an array of ConfigField into two arrays, with the first containing
 * 'main content' fields and the second containing all the other fields.
 * these two arrays can then be used to render our fields into two columns.
 **/
export const splitFieldsIntoColumns = (
  fields: ConfigField[]
): ConfigField[][] =>
  partition(isMainContentField, fields).filter(column => column.length > 0)

/**
 * takes a ConfigField and returns an appropriate empty value
 * for that field.
 **/
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

export const isRepeatableCollectionItem = (
  configItem: TopLevelConfigItem
): boolean => "folder" in configItem

export const isSingletonCollectionItem = (
  configItem: EditableConfigItem
): boolean => "file" in configItem

/*
 * Translates page content form values into a payload that our REST API understands.
 */
export const contentFormValuesToPayload = (
  values: SiteFormValues,
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

/**
 * Translates site content REST API data into initial values that our forms understand.
 **/
export const contentInitialValues = (
  content: WebsiteContent,
  fields: ConfigField[]
): SiteFormValues => {
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
      values[field.name] = metadata[field.name] ?? defaultFor(field)
    }
  }
  return values
}

/**
 * returns values for the ContentForm when we're instantiating it anew.
 **/
export const newInitialValues = (fields: ConfigField[]): SiteFormValues =>
  Object.fromEntries(
    fields.map((field: ConfigField) => [
      field.name,
      field.default ?? defaultFor(field)
    ])
  )

const defaultFor = (field: ConfigField): boolean | string | string[] | null => {
  switch (field.widget) {
  case WidgetVariant.Boolean:
    return false
  case WidgetVariant.Select:
    return field.multiple ? [] : ""
  case WidgetVariant.File:
    return null
  default:
    return ""
  }
}

/*
 * Should field data be sent to the server?
 */
export function fieldHasData(
  field: ConfigField,
  values: SiteFormValues
): boolean {
  if (!field.condition) {
    return true
  }

  const condition = field.condition
  return values[condition.field] === condition.equals
}

/**
 * Should field, label, and validation be displayed in the UI?
 **/
export const fieldIsVisible = (
  field: ConfigField,
  values: SiteFormValues
): boolean => field.widget !== "hidden" && fieldHasData(field, values)
