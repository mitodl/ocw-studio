import React from "react"
import { Formik, Form, ErrorMessage, Field, FormikHelpers } from "formik"
import * as yup from "yup"

import { EDITABLE_ROLES, ROLE_LABELS } from "../../constants"

import {
  WebsiteCollaborator,
  WebsiteCollaboratorForm
} from "../../types/websites"

interface Props {
  onSubmit: (
    values: WebsiteCollaboratorForm,
    formikHelpers: FormikHelpers<any>
  ) => void
  collaborator: WebsiteCollaborator
}

export const collaboratorValidation = yup.object().shape({
  role: yup
    .string()
    .label("Role")
    .required()
})

const getInitialValues = (collaborator: WebsiteCollaborator) => ({
  role: collaborator.role
})

export default function SiteCollaboratorEditForm({
  collaborator,
  onSubmit
}: Props): JSX.Element | null {
  return (
    <Formik
      // @ts-ignore
      onSubmit={onSubmit}
      initialValues={getInitialValues(collaborator)}
      validationSchema={collaboratorValidation}
    >
      {({ isSubmitting, status }) => (
        <Form>
          <div className="form-group">
            <label htmlFor="role" className="font-weight-bold">
              Role*
            </label>

            <Field component="select" name="role" className="form-control">
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
