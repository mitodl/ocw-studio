import * as yup from "yup"
import { SchemaOf, setLocale } from "yup"

import { ConfigField, ConfigItem, WidgetVariant } from "../../types/websites"

// This is added to properly handle file fields, which can have a "null" value
setLocale({
  mixed: {
    notType: "${path} is a required field."
  }
})

export const getFieldSchema = (field: ConfigField): SchemaOf<any> => {
  switch (field.widget) {
  case WidgetVariant.Select:
    if (field.multiple) {
      return yup.array()
    } else {
      return yup.string()
    }
  case WidgetVariant.File:
    return yup.mixed()
  case WidgetVariant.String:
  case WidgetVariant.Text:
  case WidgetVariant.Markdown:
  default:
    return yup.string()
  }
}

export const getContentSchema = (configItem: ConfigItem): SchemaOf<any> => {
  const yupObjectShape = {}
  configItem.fields.forEach(field => {
    const yupField = getFieldSchema(field)
    yupObjectShape[field.name] = yupField.label(field.label)
    if (field.required) {
      switch (field.widget) {
      case WidgetVariant.File:
        yupObjectShape[field.name] = yupObjectShape[field.name]
          .label(field.label)
          .required()
        break
      default:
        yupObjectShape[field.name] = yupObjectShape[field.name].required()
        break
      }
    }
  })
  return yup.object().shape(yupObjectShape)
}
