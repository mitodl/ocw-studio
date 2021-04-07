import React from "react"
import { Formik, Form, ErrorMessage, Field, FormikHelpers } from "formik"
import * as yup from "yup"

import { FormError } from "./FormError"
import { EDITABLE_ROLES, ROLE_LABELS } from "../../constants"

import {
  WebsiteCollaborator,
  WebsiteCollaboratorFormData
} from "../../types/websites"
import SelectField from "../widgets/SelectField"

interface Props {
  collaborator?: WebsiteCollaborator
  onSubmit: (
    values: WebsiteCollaboratorFormData,
    formikHelpers: FormikHelpers<any>
  ) => void
}

export const roleValidation = {
  role: yup
    .string()
    .label("Role")
    .required()
}

export const emailValidation = {
  email: yup
    .string()
    .email()
    .label("Email")
    .required()
}

const getInitialValues = (collaborator: WebsiteCollaborator | null) =>
  collaborator ? { role: collaborator.role } : { email: "", role: "" }

export default function SiteCollaboratorForm({
  collaborator,
  onSubmit
}: Props): JSX.Element | null {
  const collaboratorValidation = yup
    .object()
    .shape(
      collaborator ?
        { ...roleValidation } :
        { ...roleValidation, ...emailValidation }
    )

  return (
    <Formik
      onSubmit={onSubmit}
      // @ts-ignore
      initialValues={getInitialValues(collaborator || null)}
      validationSchema={collaboratorValidation}
    >
      {({ isSubmitting, values, status }) => (
        <Form>
          {collaborator ? null : (
            <div className="form-group">
              <label htmlFor="email">Email</label>
              <Field
                name="email"
                className="form-control"
                type="email"
                value={values.email}
              />
              <ErrorMessage name="email" component={FormError} />
            </div>
          )}
          <div className="form-group">
            <label htmlFor="role">Role*</label>
            <Field
              as={SelectField}
              name="role"
              className="form-control"
              options={[
                { label: "-----", value: "" },
                ...EDITABLE_ROLES.map((role: string) => ({
                  label: ROLE_LABELS[role],
                  value: role
                }))
              ]}
            />
            <ErrorMessage name="role" component={FormError} />
          </div>
          <div className="form-group d-flex justify-content-end">
            <button
              type="submit"
              className="btn blue-button"
              disabled={isSubmitting}
            >
              Save
            </button>
          </div>
          {status && <div className="form-error">{status}</div>}
        </Form>
      )}
    </Formik>
  )
}
