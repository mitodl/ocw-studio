import { ErrorMessage, Field } from "formik"
import React from "react"

import { FormError } from "./FormError"
import { componentFromWidget, widgetExtraProps } from "../../lib/site_content"

import { ConfigField, WebsiteContent } from "../../types/websites"

interface Props {
  field: ConfigField
  contentContext: WebsiteContent[] | null
  onChange?: (e: React.ChangeEvent<any>) => void
}

/**
 * Field for editing any type of site content
 */
export default function SiteContentField({
  field,
  contentContext,
  onChange
}: Props): JSX.Element {
  const extraProps = widgetExtraProps(field)
  const component = componentFromWidget(field)

  if (component && typeof component !== "string") {
    extraProps.contentContext = contentContext
  }

  return (
    <div className="form-group">
      <label htmlFor={field.name}>{field.label}</label>
      <Field
        as={component}
        name={field.name}
        className="form-control"
        onChange={onChange}
        {...extraProps}
      />
      {field.help && <span className="help-text">{field.help}</span>}
      <ErrorMessage name={field.name} component={FormError} />
    </div>
  )
}
