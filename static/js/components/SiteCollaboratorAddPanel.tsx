import React from "react"
import { useMutation } from "redux-query-react"
import { RouteComponentProps, useRouteMatch } from "react-router-dom"
import { FormikHelpers } from "formik"
import { is } from "ramda"

import SiteCollaboratorAddForm from "./forms/SiteCollaboratorAddForm"
import { siteCollaboratorsUrl } from "../lib/urls"
import { getResponseBodyError, isErrorResponse } from "../lib/util"
import { createWebsiteCollaboratorMutation } from "../query-configs/websites"

import { WebsiteCollaboratorForm } from "../types/websites"

interface MatchParams {
  username: string
  name: string
}

type Props = RouteComponentProps<Record<string, never>>

export default function SiteCollaboratorAddPanel({
  history
}: Props): JSX.Element | null {
  const match = useRouteMatch<MatchParams>()
  const { name } = match.params

  const [collaboratorQueryState, addCollaborator] = useMutation(
    createWebsiteCollaboratorMutation
  )

  const onSubmit = async (
    values: WebsiteCollaboratorForm,
    {
      setSubmitting,
      setErrors,
      setStatus
    }: FormikHelpers<WebsiteCollaboratorForm>
  ) => {
    if (collaboratorQueryState.isPending) {
      return
    }
    const response = await addCollaborator(name, values)
    if (!response) {
      return
    }
    if (isErrorResponse(response)) {
      const errors = getResponseBodyError(response)
      if (!errors) {
        return
      } else if (is(String, errors)) {
        // Non-field error
        setStatus(errors)
      } else {
        setErrors({
          // @ts-ignore
          email: errors.email,
          // @ts-ignore
          role:  errors.role
        })
      }
      return
    }
    setSubmitting(false)
    history.push(siteCollaboratorsUrl(name))
  }

  return (
    <div className="narrow-page-body m-3">
      <h3>Add Collaborator</h3>
      <div className="form-container m-3 p-3">
        <SiteCollaboratorAddForm onSubmit={onSubmit}></SiteCollaboratorAddForm>
      </div>
    </div>
  )
}
