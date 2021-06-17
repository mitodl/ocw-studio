import { ComponentType, ElementType } from "react"
import { evolve, map, partition, pick } from "ramda"

import MarkdownEditor from "../components/widgets/MarkdownEditor"
import FileUploadField from "../components/widgets/FileUploadField"
import SelectField from "../components/widgets/SelectField"
import BooleanField from "../components/widgets/BooleanField"
import RelationField from "../components/widgets/RelationField"

import { objectToFormData } from "./util"
import {
  MAIN_PAGE_CONTENT_DB_FIELD,
  MAIN_PAGE_CONTENT_FIELD
} from "../constants"

import {
  BaseConfigItem,
  ConfigField,
  EditableConfigItem,
  RepeatableConfigItem,
  SingletonConfigItem,
  StringConfigField,
  WebsiteContent,
  WidgetVariant
} from "../types/websites"
import {
  SiteFormPrimitive,
  SiteFormValue,
  SiteFormValues
} from "../types/forms"

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
  case WidgetVariant.Relation:
    return RelationField
  default:
    return "input"
  }
}

const SELECT_EXTRA_PROPS = ["options", "multiple", "max", "min"]

const RELATION_EXTRA_PROPS = [
  "collection",
  "display_field",
  "max",
  "min",
  "multiple",
  "filter"
]

export const DEFAULT_TITLE_FIELD: StringConfigField = {
  name:     "title",
  label:    "Title",
  widget:   WidgetVariant.String,
  required: true
}

/**
 * Returns extra props that should be provided to the `Field`
 * component, based on what type of widget we're dealing with.
 **/
export function widgetExtraProps(field: ConfigField): Record<string, any> {
  switch (field.widget) {
  case WidgetVariant.Select:
    return pick(SELECT_EXTRA_PROPS, field)
  case WidgetVariant.Markdown:
    return { minimal: field.minimal ?? false }
  case WidgetVariant.Relation:
    return pick(RELATION_EXTRA_PROPS, field)
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
const emptyValue = (field: ConfigField): SiteFormValue => {
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
  configItem: BaseConfigItem
): configItem is RepeatableConfigItem => "folder" in configItem

export const isSingletonCollectionItem = (
  configItem: BaseConfigItem
): configItem is SingletonConfigItem => "file" in configItem

/**
 * Translates page content form values into a payload that our REST API understands.
 **/
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

  let hasFileUpload = false
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
      } else if (value instanceof File) {
        payload["file"] = value
        hasFileUpload = true
      } else {
        metadata[field.name] = value
      }
    }
  }

  if (Object.keys(metadata).length > 0) {
    payload["metadata"] = metadata
  }

  return hasFileUpload ? objectToFormData(payload) : payload
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
    } else {
      values[field.name] = metadata[field.name] ?? defaultForField(field)
    }
  }
  return values
}

/**
 * Returns appropriate values for the ContentForm when we're instantiating it
 * anew.
 **/
export const newInitialValues = (fields: ConfigField[]): SiteFormValues =>
  Object.fromEntries(
    fields.map((field: ConfigField) => [
      field.name,
      field.widget === WidgetVariant.Object ?
        newInitialValues(field.fields) :
        field.default ?? defaultForField(field)
    ])
  )

/**
 * Returns a default value appropriate for a given `ConfigField`. This mainly
 * switches of off `field.widget: WidgetVariant` but also looks at other props
 * like `.multiple: boolean` on `WidgetVariant.Select` fields, for instance.
 **/
const defaultForField = (field: ConfigField): SiteFormValue => {
  switch (field.widget) {
  case WidgetVariant.Boolean:
    return false
  case WidgetVariant.Relation:
  case WidgetVariant.Select:
    return field.multiple ? [] : ""
  case WidgetVariant.File:
    return null
  case WidgetVariant.Object:
    return Object.fromEntries(
      field.fields.map(field => [
        field.name,
          // the `as` is fully justified here: we don't want to allow
          // doubly-nested fields (for now!) so calling `defaultFor` on a
          // nested field *should* only return SiteFormPrimitive (i.e. boolean,
          // string, etc) and *not* another nested
          // Record<string, SiteFormPrimitive>
          defaultForField(field) as SiteFormPrimitive
      ])
    )
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

/**
 * For editing nested fields in Formik we need them to be named like
 * `foo.bar`, where `foo` is the name of the object they should be nested under
 * and `bar` is the name of the field.
 *
 * For our Object widget, `foo` will be the name of the Object field and `bar`
 * will be the name of the field nested within it, so to support for instance
 * an Object field called `address` with a `zip_code` field within in we need
 * to rename the `name` property on the `zip_code` field from `"zip_code"` to
 * `"address.zip_code"`.
 *
 * This function takes an `Array<ConfigField>` and returns a new
 * `Array<ConfigField>` where all such nested fields have been appropriately
 * renamed so they can be passed down to Formik.
 **/
export const renameNestedFields = (fields: ConfigField[]): ConfigField[] =>
  fields.map((field: ConfigField) =>
    field.widget === WidgetVariant.Object ?
      evolve(
        {
          fields: map((nestedField: ConfigField) => ({
            ...nestedField,
            name: `${field.name}.${nestedField.name}`
          }))
        },
        field
      ) :
      field
  )

export const addDefaultFields = (
  configItem: EditableConfigItem
): ConfigField[] => {
  const fields = configItem.fields
  if (!isRepeatableCollectionItem(configItem)) {
    return fields
  }
  const titleField = fields.find(field => field.name === "title")
  if (titleField) {
    return fields
  }
  return [DEFAULT_TITLE_FIELD, ...fields]
}
