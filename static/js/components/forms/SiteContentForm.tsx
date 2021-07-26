import React, { useMemo } from "react"
import {
  Form,
  Formik,
  FormikHelpers,
  FormikValues,
  validateYupSchema,
  yupToFormErrors
} from "formik"

import SiteContentField from "./SiteContentField"
import ObjectField from "../widgets/ObjectField"

import {
  contentInitialValues,
  fieldIsVisible,
  newInitialValues,
  renameNestedFields,
  splitFieldsIntoColumns
} from "../../lib/site_content"

import {
  WebsiteContent,
  WidgetVariant,
  ConfigField,
  EditableConfigItem
} from "../../types/websites"
import { ContentFormType, SiteFormValues } from "../../types/forms"
import { getContentSchema } from "./validation"
import { useWebsite } from "../../context/Website"

interface Props {
  onSubmit: (
    values: any,
    formikHelpers: FormikHelpers<any>
  ) => void | Promise<any>
  fields: ConfigField[]
  configItem: EditableConfigItem
  content: WebsiteContent | null
  formType: ContentFormType
}

export default function SiteContentForm({
  onSubmit,
  fields,
  configItem,
  content,
  formType
}: Props): JSX.Element {
  const website = useWebsite()
  const initialValues: SiteFormValues = useMemo(
    () =>
      formType === ContentFormType.Add ?
        newInitialValues(fields, website) :
        contentInitialValues(content as WebsiteContent, fields, website),
    [fields, formType, content, website]
  )
  const contentContext = content?.content_context ?? null

  const renamedFields: ConfigField[] = useMemo(
    () => renameNestedFields(fields),
    [fields]
  )
  const fieldsByColumn = splitFieldsIntoColumns(renamedFields)
  const columnClass = fieldsByColumn.length === 2 ? "col-6" : "col-12"

  const validate = async (values: FormikValues) => {
    const schema = getContentSchema(configItem, values)
    try {
      await validateYupSchema(values, schema)
    } catch (e) {
      return yupToFormErrors(e)
    }
    return {}
  }

  return (
    <Formik
      onSubmit={onSubmit}
      validate={validate}
      initialValues={initialValues}
      enableReinitialize={true}
    >
      {({ isSubmitting, status, setFieldValue, values }) => (
        <Form className="row">
          {fieldsByColumn.map((columnFields, idx) => (
            <div className={columnClass} key={idx}>
              {columnFields
                .filter(field => fieldIsVisible(field, values))
                .map(field =>
                  field.widget === WidgetVariant.Object ? (
                    <ObjectField
                      field={field}
                      key={field.name}
                      setFieldValue={setFieldValue}
                      contentContext={contentContext}
                    />
                  ) : (
                    <SiteContentField
                      field={field}
                      key={field.name}
                      setFieldValue={setFieldValue}
                      contentContext={contentContext}
                    />
                  )
                )}
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
