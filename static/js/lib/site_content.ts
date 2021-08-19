import { ComponentType, ElementType } from "react"
import { evolve, map, partition, pick } from "ramda"

import MarkdownEditor from "../components/widgets/MarkdownEditor"
import FileUploadField from "../components/widgets/FileUploadField"
import SelectField from "../components/widgets/SelectField"
import BooleanField from "../components/widgets/BooleanField"
import RelationField from "../components/widgets/RelationField"
import MenuField from "../components/widgets/MenuField"
import HierarchicalSelectField from "../components/widgets/HierarchicalSelectField"

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
  Website,
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
  case WidgetVariant.Menu:
    return MenuField
  case WidgetVariant.HierarchicalSelect:
    return HierarchicalSelectField
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
  "filter",
  "website"
]
const MENU_EXTRA_PROPS = ["collections"]
const HIERARCHICAL_SELECT_EXTRA_PROPS = ["options_map", "levels"]

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
    return {
      minimal: field.minimal ?? false,
      attach:  field.attach ?? undefined
    }
  case WidgetVariant.Relation:
    return pick(RELATION_EXTRA_PROPS, field)
  case WidgetVariant.Menu:
    return pick(MENU_EXTRA_PROPS, field)
  case WidgetVariant.HierarchicalSelect:
    return pick(HIERARCHICAL_SELECT_EXTRA_PROPS, field)
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

export const isRepeatableCollectionItem = (
  configItem: BaseConfigItem
): configItem is RepeatableConfigItem => "folder" in configItem

export const isSingletonCollectionItem = (
  configItem: BaseConfigItem
): configItem is SingletonConfigItem => "file" in configItem

/**
 * Creates a value for a payload to be sent to the server, for a given field. This is used by to
 * contentFormValuesForPayload to figure out what should go in the payload for a field and nested fields.
 */
const contentFormValueForField = (
  field: ConfigField,
  parentField: ConfigField | null,
  values: SiteFormValues,
  website: Website
): SiteFormValue => {
  if (!fieldHasData(field, values)) {
    return defaultForField(field, website)
  }

  if (field.widget === WidgetVariant.Object) {
    return Object.fromEntries(
      field.fields.map(innerField => [
        innerField.name,
        contentFormValueForField(
          innerField,
          field,
          values,
          website
        ) as SiteFormPrimitive
      ])
    )
  } else if (field.widget === WidgetVariant.Hidden) {
    return field.default
  } else {
    if (parentField) {
      return (values[parentField.name] ?? {})[field.name]
    } else {
      return values[field.name]
    }
  }
}

/**
 * Translates page content form values into a payload that our REST API understands.
 **/
export const contentFormValuesToPayload = (
  values: SiteFormValues,
  fields: ConfigField[],
  website: Website
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
    const value = contentFormValueForField(field, null, values, website)

    if (value !== undefined) {
      // Our API expects these bits of data as top-level keys in the payload:
      // (1) main page content in markdown, (2) title, (3) a file. None of those values are required.
      // All other values are nested under the "metadata" key.
      if (isMainContentField(field)) {
        payload[MAIN_PAGE_CONTENT_DB_FIELD] = value
      } else if (field.name === "title") {
        payload[field.name] = value
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
  fields: ConfigField[],
  website: Website
): SiteFormValues => {
  const values = {}
  const metadata = content.metadata ?? {}

  for (const field of fields) {
    if (isMainContentField(field)) {
      values[field.name] = content.markdown ?? ""
    } else if (field.name === "title") {
      values[field.name] = content[field.name] ?? ""
    } else if (field.widget === WidgetVariant.File) {
      values[field.name] = content[field.name] ?? null
    } else {
      values[field.name] =
        metadata[field.name] ?? defaultForField(field, website)
    }
  }
  return values
}

/**
 * Returns appropriate values for the ContentForm when we're instantiating it
 * anew.
 **/
export const newInitialValues = (
  fields: ConfigField[],
  website: Website
): SiteFormValues =>
  Object.fromEntries(
    fields.map((field: ConfigField) => [
      field.name,
      field.widget === WidgetVariant.Object ?
        newInitialValues(field.fields, website) :
        field.default ?? defaultForField(field, website)
    ])
  )

/**
 * Returns a default value appropriate for a given `ConfigField`. This mainly
 * switches of off `field.widget: WidgetVariant` but also looks at other props
 * like `.multiple: boolean` on `WidgetVariant.Select` fields, for instance.
 **/
const defaultForField = (
  field: ConfigField,
  website: Website
): SiteFormValue => {
  switch (field.widget) {
  case WidgetVariant.Boolean:
    return false
  case WidgetVariant.Relation:
    return {
      website: website.name,
      content: field.multiple ? [] : ""
    }
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
          defaultForField(field, website) as SiteFormPrimitive
      ])
    )
  case WidgetVariant.HierarchicalSelect:
    return []
  case WidgetVariant.Menu:
    return []
  default:
    return ""
  }
}

/*
 * Should field data be sent to the server?
 */
export const fieldHasData = (
  field: ConfigField,
  values: SiteFormValues
): boolean => {
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
  fields.map((field: ConfigField) => {
    switch (field.widget) {
    case WidgetVariant.Object:
      return evolve(
        {
          fields: map((nestedField: ConfigField) => ({
            ...nestedField,
            name: `${field.name}.${nestedField.name}`
          }))
        },
        field
      )
    case WidgetVariant.Relation:
      return {
        ...field,
        name: `${field.name}.content`
      }
    default:
      return field
    }
  })

export function addDefaultFields(
  configItem: RepeatableConfigItem
): RepeatableConfigItem
export function addDefaultFields(
  configItem: SingletonConfigItem
): SingletonConfigItem
export function addDefaultFields(
  configItem: EditableConfigItem
): EditableConfigItem {
  const fields = configItem.fields
  if (!isRepeatableCollectionItem(configItem)) {
    return configItem
  }
  const titleField = fields.find(field => field.name === "title")
  if (titleField) {
    return configItem
  }
  return {
    ...configItem,
    fields: [DEFAULT_TITLE_FIELD, ...fields]
  }
}

export const needsContentContext = (fields: ConfigField[]): boolean => {
  for (const field of fields) {
    if (
      field.widget === WidgetVariant.Relation ||
      field.widget === WidgetVariant.Menu
    ) {
      return true
    } else if (field.widget === WidgetVariant.Object) {
      return needsContentContext(field.fields)
    }
  }
  return false
}
