import React from "react"
import { Form, Formik, FormikHelpers } from "formik"

import SiteContentField from "./SiteContentField"
import { getContentSchema } from "./validation"
import { newInitialValues } from "../../lib/site_content"

import { ConfigItem } from "../../types/websites"

interface Props {
  onSubmit: (
    values: any,
    formikHelpers: FormikHelpers<any>
  ) => void | Promise<any>
  configItem: ConfigItem
}
export default function SiteAddContentForm({
  onSubmit,
  configItem
}: Props): JSX.Element {
  const fields = configItem.fields
  const initialValues = newInitialValues(fields)
  const schema = getContentSchema(configItem)

  const fieldsByColumn = [
    fields.filter(field => field.widget === "markdown"),
    fields.filter(field => field.widget !== "markdown")
  ]

  return (
    <Formik
      onSubmit={onSubmit}
      validationSchema={schema}
      initialValues={initialValues}
    >
      {({ isSubmitting, status, setFieldValue }) => (
        <Form className="row">
          <div className="col-6">
            {fieldsByColumn[0].map(configField => (
              <SiteContentField key={configField.name} field={configField} />
            ))}
          </div>
          <div className="col-6">
            {fieldsByColumn[1].map(configField => (
              <SiteContentField
                key={configField.name}
                field={configField}
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
          </div>
        </Form>
      )}
    </Formik>
  )
}
