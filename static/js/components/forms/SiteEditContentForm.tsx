import * as React from "react"
import { Formik, Form, FormikHelpers } from "formik"

import SiteContentField from "./SiteContentField"
import { contentInitialValues } from "../../lib/site_content"
import { getContentSchema } from "./validation"

import { ConfigItem, WebsiteContent } from "../../types/websites"

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

export default function SiteEditContentForm({
  onSubmit,
  configItem,
  content
}: Props): JSX.Element {
  const fields = configItem.fields
  const initialValues: SiteFormValues = contentInitialValues(content, fields)
  const schema = getContentSchema(configItem)

  return (
    <Formik
      onSubmit={onSubmit}
      validationSchema={schema}
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
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-5 btn blue-button"
            >
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
