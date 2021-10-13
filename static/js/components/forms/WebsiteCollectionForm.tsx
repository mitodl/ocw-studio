import React from "react"
import { Form, Formik, Field, ErrorMessage } from "formik"

import { FormError } from "./FormError"
import { WebsiteCollectionFormFields, SubmitFunc } from "../../types/forms"
import { WebsiteCollectionFormSchema } from "./validation"

interface Props {
  onSubmit: SubmitFunc
  initialValues: WebsiteCollectionFormFields
}

export default function WebsiteCollectionForm(props: Props): JSX.Element {
  const { onSubmit, initialValues } = props

  return (
    <Formik
      onSubmit={onSubmit}
      initialValues={initialValues}
      validationSchema={WebsiteCollectionFormSchema}
    >
      {() => (
        <Form>
          <div className="form-group">
            <label htmlFor="title">Title</label>
            <Field
              className="form-control"
              type="string"
              name="title"
              placeholder="Title"
            />
            <ErrorMessage name="title" component={FormError} />
          </div>
          <div className="form-group">
            <label htmlFor="description">Description</label>
            <Field
              className="form-control"
              type="string"
              name="description"
              placeholder="Description"
            />
            <ErrorMessage name="description" component={FormError} />
          </div>
          <div className="form-group d-flex w-100 justify-content-end">
            <button type="submit" className="px-5 btn cyan-button">
              Save
            </button>
          </div>
        </Form>
      )}
    </Formik>
  )
}
