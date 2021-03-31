import { ErrorMessage, Field } from "formik"
import React from "react"

import { FormError } from "./FormError"
import { componentFromWidget } from "../../lib/site_content"

import { ConfigField } from "../../types/websites"

interface Props {
  field: ConfigField
  setFieldValue?: (key: string, value: File | null) => void
}

export default function SiteContentField({
  field,
  setFieldValue
}: Props): JSX.Element {
  let extraProps
  switch (field.widget) {
  case "file":
    extraProps = { setFieldValue }
    break
  case "select":
    extraProps = {}
    for (const fieldName of ["options", "multiple", "max", "min"]) {
      extraProps[fieldName] = field[fieldName]
    }
    break
  default:
    extraProps = {}
    break
  }

  return (
    <div className="form-group">
      <label htmlFor={field.name}>{field.label}</label>
      <Field
        as={componentFromWidget(field)}
        name={field.name}
        className="form-control"
        {...extraProps}
      />
      {field.help && <span className="help-text">{field.help}</span>}
      <ErrorMessage name={field.name} component={FormError} />
    </div>
  )
}
