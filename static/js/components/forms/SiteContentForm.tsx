import * as React from "react"
import { Formik, Form, FormikHelpers } from "formik"

import SiteContentField from "./SiteContentField"
import {contentInitialValues, newInitialValues, isMainContentField } from "../../lib/site_content"
import { getContentSchema } from "./validation"

import {ConfigItem, WebsiteContent} from "../../types/websites"
import {ContentFormType} from "../SiteContent";

export type SiteFormValues = Record<string, string>

type Props = {
  onSubmit: (
    values: any,
    formikHelpers: FormikHelpers<any>
  ) => void | Promise<any>
  configItem: ConfigItem
  content: WebsiteContent,
  formType: ContentFormType
}

export default function SiteContentForm({
  onSubmit,
  configItem,
  content,
  formType
}: Props): JSX.Element {
  const fields = configItem.fields
  const initialValues: SiteFormValues = formType === ContentFormType.Add ? newInitialValues(fields) : contentInitialValues(content, fields)
  const schema = getContentSchema(configItem)

  const mainContentField = fields.find(field => isMainContentField(field))
  const fieldsByColumn = mainContentField ? [[mainContentField], fields.filter(field => !isMainContentField(field))] : [fields]
  const columnClasses = fieldsByColumn.length === 2 ? "col-6" : "col-12"
  const buttonColumnIndex = fieldsByColumn.length - 1

  return (
    <Formik
      onSubmit={onSubmit}
      validationSchema={schema}
      initialValues={initialValues}
    >
      {({ isSubmitting, status, setFieldValue }) => (
        <Form className="row">
          {fieldsByColumn.map((columnFields, idx) => (
            <div className={columnClasses[idx]} key={idx}>
              {columnFields.map(field => (
                <SiteContentField
                  field={field}
                  key={field.name}
                  setFieldValue={setFieldValue}
                />
              ))}
              {buttonColumnIndex === idx ? (
                <>
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
                </>
              ) : null}
            </div>
          ))}
        </Form>
      )}
    </Formik>
  )
}
