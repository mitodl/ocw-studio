import * as React from "react"
import { Formik, Form, FormikHelpers } from "formik"
import * as yup from "yup"

import { contentInitialValues } from "../../lib/site_content"

import { ConfigItem, WebsiteContent } from "../../types/websites"
import SiteContentField from "./SiteContentField"

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
      {({ isSubmitting, status, setFieldValue }) => (
        <Form>
          {fields.map(field => (
            <SiteContentField
              field={field}
              key={field.name}
              setFieldValue={setFieldValue}
            />
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
