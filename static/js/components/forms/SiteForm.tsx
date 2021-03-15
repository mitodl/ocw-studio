import * as React from "react"
import { Formik, Form, ErrorMessage, Field, FormikHelpers } from "formik"
import * as yup from "yup"

import { WebsiteStarter } from "../../types/websites"

export interface SiteFormValues {
  title: string
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
  starter: yup.number().required()
})

export const SiteForm = ({
  onSubmit,
  websiteStarters
}: Props): JSX.Element | null => {
  const initialValues: SiteFormValues = {
    title:   "",
    starter: websiteStarters.length > 0 ? websiteStarters[0].id : 0
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
            <ErrorMessage name="title" component="div" />
          </div>
          <div className="form-group">
            <label htmlFor="starter">Starter*</label>
            <Field component="select" name="starter" className="form-control">
              {websiteStarters.length > 0 ? (
                websiteStarters.map((starter, i) => (
                  <option key={i} value={starter.id}>
                    {starter.name}
                  </option>
                ))
              ) : (
                // Empty option to prevent build warning/errors
                <option key={0} value={0} />
              )}
            </Field>
            <ErrorMessage name="starter" component="div" />
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
