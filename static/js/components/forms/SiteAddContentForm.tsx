import React from "react"
import { Form, Formik, FormikHelpers } from "formik"

import SiteContentField from "./SiteContentField"
import { getContentSchema } from "./validation"
import { fieldIsVisible, newInitialValues } from "../../lib/site_content"

import { ConfigItem, WidgetVariant } from "../../types/websites"

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

  const leftColumn = fields.filter(
    field => field.widget === WidgetVariant.Markdown
  )
  const rightColumn = fields.filter(
    field => field.widget !== WidgetVariant.Markdown
  )

  return (
    <Formik
      onSubmit={onSubmit}
      validationSchema={schema}
      initialValues={initialValues}
    >
      {({ isSubmitting, status, setFieldValue, values }) => (
        <Form className="row">
          <div className="col-6">
            {leftColumn.map(field =>
              fieldIsVisible(field, values) ? (
                <SiteContentField
                  key={field.name}
                  field={field}
                  setFieldValue={setFieldValue}
                />
              ) : null
            )}
          </div>
          <div className="col-6">
            {rightColumn.map(field =>
              fieldIsVisible(field, values) ? (
                <SiteContentField
                  key={field.name}
                  field={field}
                  setFieldValue={setFieldValue}
                />
              ) : null
            )}
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
