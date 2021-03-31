import { ErrorMessage, Field } from "formik"
import React from "react"

import { FormError } from "./FormError"
import { componentFromWidget, widgetExtraProps } from "../../lib/site_content"

import { ConfigField, WidgetVariant } from "../../types/websites"

interface Props {
  field: ConfigField
  setFieldValue?: (key: string, value: File | null) => void
}

/**
 * Field for editing any type of site content
 */
export default function SiteContentField({
  field,
  setFieldValue
}: Props): JSX.Element {
  const extraProps = widgetExtraProps(field)

  if (
    field.widget === WidgetVariant.File ||
    field.widget === WidgetVariant.Boolean
  ) {
    extraProps.setFieldValue = setFieldValue
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
