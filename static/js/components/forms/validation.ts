import * as yup from "yup"
import { SchemaOf, setLocale } from "yup"

import { ConfigItem } from "../../types/websites"

// This is added to properly handle file fields, which can have a "null" value
setLocale({
  mixed: {
    notType: "${path} is a required field."
  }
})

const defaultYupField = yup.string()
const widgetToYupMap = {
  string:   yup.string(),
  text:     yup.string(),
  markdown: yup.string(),
  file:     yup.object().shape({
    name: yup.string()
  })
}

export const getContentSchema = (configItem: ConfigItem): SchemaOf<any> => {
  const yupObjectShape = {}
  configItem.fields.forEach(field => {
    const yupField = widgetToYupMap[field.widget] || defaultYupField
    yupObjectShape[field.name] = yupField.label(field.label)
    if (field.required) {
      switch (field.widget) {
      case "file":
        yupObjectShape[field.name] = yupObjectShape[field.name].fields.name
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
