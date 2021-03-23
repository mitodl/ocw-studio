import * as React from "react"
import { Formik, FormikHelpers, Form, ErrorMessage, Field } from "formik"
import * as yup from "yup"
import slugify from "slugify"

import { WebsiteStarter } from "../../types/websites"

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
            <ErrorMessage name="title" component="div" />
          </div>
          <div className="form-group">
            <label htmlFor="name">URL*</label>
            <Field type="text" name="name" className="form-control" />
            <ErrorMessage name="name" component="div" />
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
