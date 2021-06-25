import * as yup from "yup"
import { ArraySchema, setLocale } from "yup"

import {
  fieldIsVisible,
  isRepeatableCollectionItem
} from "../../lib/site_content"

import {
  ConfigField,
  ConfigItem,
  RelationConfigField,
  SelectConfigField,
  WidgetVariant,
  EditableConfigItem
} from "../../types/websites"
import { FormSchema } from "../../types/forms"
import { FormikValues } from "formik"

// This is added to properly handle file fields, which can have a "null" value
setLocale({
  mixed: {
    notType: "${path} is a required field."
  }
})

const defaultTitleFieldSchema = yup
  .string()
  .required()
  .label("Title")

const minMax = (
  schema: ArraySchema<any>,
  field: RelationConfigField | SelectConfigField
) => {
  if (field.min) {
    schema = schema.min(
      field.min,
      `${field.name} must have at least ${field.min} ${
        field.min === 1 ? "entry" : "entries"
      }.`
    )
  }
  if (field.max) {
    schema = schema.max(
      field.max,
      `${field.name} may have at most ${field.max} entries.`
    )
  }
  return schema
}

/**
 * Obtain the schema for a given field. This mainly switches on the
 * WidgetVariant, but also looks at some other props like `min`, `max`,
 * `required`, and `label`.
 **/
export const getFieldSchema = (field: ConfigField): FormSchema => {
  let schema

  switch (field.widget) {
  case WidgetVariant.Relation: {
    if (field.multiple) {
      schema = yup.object().shape({
        // @ts-ignore
        content: minMax(yup.array(), field)
      })
    } else {
      schema = yup.object().shape({
        content: yup.string()
      })
    }
    break
  }
  case WidgetVariant.Select: {
    if (field.multiple) {
      schema = minMax(yup.array(), field)
    } else {
      schema = yup.string()
    }

    break
  }
  case WidgetVariant.File: {
    schema = yup.mixed()
    break
  }
  case WidgetVariant.Object: {
    schema = yup
      .object()
      .shape(
        Object.fromEntries(
          field.fields.map(field => [field.name, getFieldSchema(field)])
        )
      )
    break
  }
  case WidgetVariant.String:
  case WidgetVariant.Text:
  case WidgetVariant.Markdown:
  default:
    schema = yup.string()
  }

  if (field.required) {
    schema = schema.required()
  }
  schema = schema.label(field.label)
  return schema
}

/**
 * Given a ConfigItem (with ConfigFields defined on it) return
 * a Yup validation schema which will validate a form for those fields.
 **/
export const getContentSchema = (
  configItem: ConfigItem | EditableConfigItem,
  values: FormikValues
): FormSchema => {
  const titleField = configItem.fields.find(field => field.name === "title")
  const yupObjectShape = Object.fromEntries(
    configItem.fields
      .filter(field => fieldIsVisible(field, values))
      .map(field => [field.name, getFieldSchema(field)])
  )
  if (isRepeatableCollectionItem(configItem) && !titleField) {
    yupObjectShape["title"] = defaultTitleFieldSchema
  }
  return yup.object().shape(yupObjectShape)
}
