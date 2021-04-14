import * as yup from "yup"
import { SchemaOf, setLocale } from "yup"

import {
  ConfigField,
  ConfigItem,
  WidgetVariant,
  EditableConfigItem
} from "../../types/websites"

// This is added to properly handle file fields, which can have a "null" value
setLocale({
  mixed: {
    notType: "${path} is a required field."
  }
})

type Schema = SchemaOf<any>

/**
 * Obtain the schema for a given field. This mainly switches on the
 * WidgetVariant, but also looks at some other props like `min`, `max`,
 * `required`, and `label`.
 **/
export const getFieldSchema = (field: ConfigField): Schema => {
  let schema

  switch (field.widget) {
  case WidgetVariant.Select: {
    if (field.multiple) {
      schema = yup.array()

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
    } else {
      schema = yup.string()
    }

    break
  }
  case WidgetVariant.File: {
    schema = yup.mixed()
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
  configItem: ConfigItem | EditableConfigItem
): Schema => {
  const yupObjectShape = Object.fromEntries(
    configItem.fields.map(field => [field.name, getFieldSchema(field)])
  )
  return yup.object().shape(yupObjectShape)
}
