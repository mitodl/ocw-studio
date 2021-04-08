import * as React from "react"
import { Form, Formik, FormikHelpers } from "formik"

import SiteContentField from "./SiteContentField"

import {
  contentInitialValues,
  fieldIsVisible,
  newInitialValues,
  splitFieldsIntoColumns
} from "../../lib/site_content"
import { getContentSchema } from "./validation"

import { EditableConfigItem, WebsiteContent } from "../../types/websites"
import { ContentFormType, SiteFormValues } from "../../types/forms"

interface Props {
  onSubmit: (
    values: any,
    formikHelpers: FormikHelpers<any>
  ) => void | Promise<any>
  configItem: EditableConfigItem
  content: WebsiteContent
  formType: ContentFormType
}

export default function SiteContentForm({
  onSubmit,
  configItem,
  content,
  formType
}: Props): JSX.Element {
  const { fields } = configItem
  const initialValues: SiteFormValues =
    formType === ContentFormType.Add ?
      newInitialValues(fields) :
      contentInitialValues(content, fields)
  const schema = getContentSchema(configItem)

  const fieldsByColumn = splitFieldsIntoColumns(fields)
  const columnClass = fieldsByColumn.length === 2 ? "col-6" : "col-12"

  return (
    <Formik
      onSubmit={onSubmit}
      validationSchema={schema}
      initialValues={initialValues}
    >
      {({ isSubmitting, status, setFieldValue, values }) => (
        <Form className="row">
          {fieldsByColumn.map((columnFields, idx) => (
            <div className={columnClass} key={idx}>
              {columnFields
                .filter(field => fieldIsVisible(field, values))
                .map(field => (
                  <SiteContentField
                    field={field}
                    key={field.name}
                    setFieldValue={setFieldValue}
                  />
                ))}
            </div>
          ))}
          <div className="form-group d-flex w-100 justify-content-end">
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
