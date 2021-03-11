import { ErrorMessage, Field } from "formik"
import React from "react"

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
  return (
    <div className="form-group">
      <label htmlFor={field.name} className="font-weight-bold">
        {field.label}
      </label>
      <Field
        as={componentFromWidget(field)}
        name={field.name}
        className="form-control"
        setFieldValue={setFieldValue}
      />
      <ErrorMessage name={field.name} component="div" />
    </div>
  )
}
