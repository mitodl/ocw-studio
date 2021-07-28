import { ErrorMessage, Field } from "formik"
import React from "react"

import { FormError } from "./FormError"
import { componentFromWidget, widgetExtraProps } from "../../lib/site_content"

import { ConfigField, WebsiteContent } from "../../types/websites"

interface Props {
  field: ConfigField
  setFieldValue: (key: string, value: File | null) => void
  contentContext: WebsiteContent[] | null
}

/**
 * Field for editing any type of site content
 */
export default function SiteContentField({
  field,
  setFieldValue,
  contentContext
}: Props): JSX.Element {
  const extraProps = widgetExtraProps(field)
  const component = componentFromWidget(field)

  if (component && typeof component !== "string") {
    extraProps.setFieldValue = setFieldValue
    extraProps.contentContext = contentContext
  }

  return (
    <div className="form-group">
      <label htmlFor={field.name}>{field.label}</label>
      <Field
        as={component}
        name={field.name}
        className="form-control"
        {...extraProps}
      />
      {field.help && <span className="help-text">{field.help}</span>}
      <ErrorMessage name={field.name} component={FormError} />
    </div>
  )
}
