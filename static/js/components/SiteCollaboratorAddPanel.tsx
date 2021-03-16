import React from "react"
import { useMutation, useRequest } from "redux-query-react"
import { RouteComponentProps, useRouteMatch } from "react-router-dom"
import { FormikHelpers } from "formik"
import { is } from "ramda"

import SiteCollaboratorForm from "./forms/SiteCollaboratorForm"
import { siteCollaboratorsUrl } from "../lib/urls"
import { getResponseBodyError, isErrorResponse } from "../lib/util"
import {
  createWebsiteCollaboratorMutation,
  websiteCollaboratorsRequest
} from "../query-configs/websites"

import { WebsiteCollaboratorFormData } from "../types/websites"

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

  const [{ isPending }] = useRequest(websiteCollaboratorsRequest(name))
  const [collaboratorQueryState, addCollaborator] = useMutation(
    createWebsiteCollaboratorMutation
  )

  const onSubmit = async (
    values: WebsiteCollaboratorFormData,
    {
      setSubmitting,
      setErrors,
      setStatus
    }: FormikHelpers<WebsiteCollaboratorFormData>
  ) => {
    if (collaboratorQueryState.isPending) {
      return
    }
    if (isPending) {
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
          email: errors["email"],
          role:  errors["role"]
        })
      }
      return
    }
    setSubmitting(false)
    history.push(siteCollaboratorsUrl.param({ name }).toString())
  }

  return (
    <div className="narrow-page-body m-3">
      <h3>Add Collaborator</h3>
      <div className="form-container m-3 p-3">
        <SiteCollaboratorForm onSubmit={onSubmit}></SiteCollaboratorForm>
      </div>
    </div>
  )
}
