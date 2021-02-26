import React from "react"
import { Formik, Form, ErrorMessage, Field, FormikHelpers } from "formik"
import * as yup from "yup"
import { EDITABLE_ROLES, ROLE_LABELS } from "../../constants"

import { WebsiteCollaboratorForm } from "../../types/websites"

interface Props {
  onSubmit: (
    values: WebsiteCollaboratorForm,
    formikHelpers: FormikHelpers<any>
  ) => void
}

export const collaboratorValidation = yup.object().shape({
  email: yup
    .string()
    .email()
    .label("Email")
    .required(),
  role: yup
    .string()
    .label("Role")
    .required()
})

export default function SiteCollaboratorAddForm({
  onSubmit
}: Props): JSX.Element | null {
  return (
    <Formik
      // @ts-ignore
      onSubmit={onSubmit}
      initialValues={{ email: "", role: "" }}
      validationSchema={collaboratorValidation}
    >
      {({ isSubmitting, values, status }) => (
        <Form>
          <div className="form-group">
            <label htmlFor="email">Email</label>
            <Field
              name="email"
              className="form-control"
              type="email"
              value={values.email}
            />
            <ErrorMessage name="email" />
          </div>
          <div className="form-group">
            <label htmlFor="role" className="font-weight-bold">
              Role*
            </label>

            <Field
              component="select"
              name="role"
              className="form-control"
              value={values.role}
            >
              <option value="">-----</option>
              {EDITABLE_ROLES.map((role: string, i: number) => (
                <option key={i} value={role}>
                  {ROLE_LABELS[role]}
                </option>
              ))}
            </Field>
            <ErrorMessage name="role" />
          </div>
          <div className="form-group">
            <button type="submit" disabled={isSubmitting}>
              Save
            </button>
          </div>
          {status && <div className="form-error">{status}</div>}
        </Form>
      )}
    </Formik>
  )
}
