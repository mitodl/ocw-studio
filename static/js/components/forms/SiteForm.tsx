import * as React from "react"
import { Formik, Form, ErrorMessage, Field, FormikHelpers } from "formik"
import * as yup from "yup"
import slugify from "slugify"

import { FormError } from "./FormError"

import { WebsiteStarter } from "../../types/websites"
import SelectField from "../widgets/SelectField"

export interface SiteFormValues {
  title: string
  name: string
  starter: number | null
}

type Props = {
  onSubmit: (
    values: any,
    formikHelpers: FormikHelpers<any>
  ) => void | Promise<any>
  websiteStarters: Array<WebsiteStarter>
}

export const websiteValidation = yup.object().shape({
  title: yup
    .string()
    .label("Title")
    .trim()
    .required(),
  name: yup
    .string()
    .label("URL")
    .trim()
    .matches(/^[a-z0-9-]*$/, {
      message: "Must be lowercase & only include letters (a-z), numbers, dashes"
    })
    .required(),
  starter: yup.number().required()
})

const handleTitleChange = (handler: any) => (e: any) => {
  const { target } = e
  const { value } = target
  const computedValue = slugify(value, { strict: true }).toLowerCase()
  handler({ target })
  handler({ target: { name: "name", value: computedValue } })
}

export const SiteForm = ({
  onSubmit,
  websiteStarters
}: Props): JSX.Element | null => {
  const initialValues: SiteFormValues = {
    title:   "",
    name:    "",
    starter: websiteStarters.length > 0 ? websiteStarters[0].id : 0
  }

  return (
    <Formik
      onSubmit={onSubmit}
      validationSchema={websiteValidation}
      initialValues={initialValues}
    >
      {({ isSubmitting, handleChange, status }) => (
        <Form>
          <div className="form-group">
            <label htmlFor="title">Title*</label>
            <Field
              type="text"
              name="title"
              className="form-control"
              onChange={handleTitleChange(handleChange)}
            />
            <ErrorMessage name="title" component={FormError} />
          </div>
          <div className="form-group">
            <label htmlFor="name">URL*</label>
            <Field type="text" name="name" className="form-control" />
            <ErrorMessage name="name" component="div" />
          </div>
          <div className="form-group">
            <label htmlFor="starter">Starter*</label>
            <Field
              as={SelectField}
              name="starter"
              className="form-control"
              options={
                websiteStarters.length > 0 ?
                  websiteStarters.map(starter => ({
                    label: starter.name,
                    value: starter.id
                  })) :
                  ["0"]
              }
            />
            <ErrorMessage name="starter" component={FormError} />
          </div>
          <div className="form-group d-flex justify-content-end">
            <button
              type="submit"
              className="btn blue-button"
              disabled={isSubmitting}
            >
              Submit
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
