import * as React from "react"
import { Formik, Form, ErrorMessage, Field, FormikHelpers } from "formik"
import * as yup from "yup"

import { FormError } from "./FormError"

import { WebsiteStarter } from "../../types/websites"
import SelectField from "../widgets/SelectField"

export interface SiteFormValues {
  title: string
  short_id: string // eslint-disable-line
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
  short_id: yup
    .string()
    .label("Short ID")
    .trim()
    .lowercase()
    .max(100, "Must be <= 100 characters")
    .required(),
  starter: yup.number().required()
})

export const SiteForm = ({
  onSubmit,
  websiteStarters
}: Props): JSX.Element | null => {
  const initialValues: SiteFormValues = {
    title:    "",
    short_id: "",
    starter:  websiteStarters.length > 0 ? websiteStarters[0].id : 0
  }

  return (
    <Formik
      onSubmit={onSubmit}
      validationSchema={websiteValidation}
      initialValues={initialValues}
    >
      {({ isSubmitting, status }) => (
        <Form>
          <div className="form-group">
            <label htmlFor="title">Title*</label>
            <Field type="text" name="title" className="form-control" />
            <ErrorMessage name="title" component={FormError} />
          </div>
          <div className="form-group">
            <label htmlFor="short_id">Short ID*</label>
            <Field
              type="text"
              name="short_id"
              className="form-control"
              placeholder="Example: 6.0001-fall-2021"
            />
            <ErrorMessage name="short_id" component={FormError} />
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
