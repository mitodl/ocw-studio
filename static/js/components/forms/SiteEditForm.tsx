import * as React from "react"
import { Formik, Form, ErrorMessage, Field, FormikHelpers } from "formik"
import * as yup from "yup"

import { ConfigItem, WebsiteContent } from "../../types/websites"
import { componentFromWidget, contentInitialValues } from "../../lib/util"

export type SiteFormValues = {
  [key: string]: string
}

type Props = {
  onSubmit: (
    values: any,
    formikHelpers: FormikHelpers<any>
  ) => void | Promise<any>
  configItem: ConfigItem
  content: WebsiteContent
}

export const websiteValidation = yup.object().shape({
  title: yup
    .string()
    .label("Title")
    .trim()
    .required()
})

export default function SiteEditForm({
  onSubmit,
  configItem,
  content
}: Props): JSX.Element {
  const fields = configItem.fields
  const initialValues: SiteFormValues = contentInitialValues(content, fields)

  return (
    <Formik
      onSubmit={onSubmit}
      validationSchema={websiteValidation}
      initialValues={initialValues}
    >
      {({ isSubmitting, status }) => (
        <Form>
          {fields.map(field => (
            <div key={field.name} className="form-group">
              <label htmlFor={field.name} className="font-weight-bold">
                {field.label}
              </label>
              <Field
                as={componentFromWidget(field)}
                name={field.name}
                className="form-control"
              />
              <ErrorMessage name={field.name} component="div" />
            </div>
          ))}
          <div className="form-group d-flex justify-content-end">
            <button type="submit" disabled={isSubmitting} className="px-5">
              Save
            </button>
          </div>
          {status && (
            // Status is being used to store non-field errors
            <div className="form-error">{status}</div>
          )}
        </Form>
      )}
    </Formik>
  )
}
