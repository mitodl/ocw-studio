import React from "react"
import { useMutation, useRequest } from "redux-query-react"
import { RouteComponentProps, useRouteMatch } from "react-router-dom"
import { useSelector } from "react-redux"
import { FormikHelpers } from "formik"
import { is } from "ramda"

import SiteCollaboratorForm from "./forms/SiteCollaboratorForm"
import { siteCollaboratorsUrl } from "../lib/urls"
import { getResponseBodyError, isErrorResponse } from "../lib/util"
import {
  editWebsiteCollaboratorMutation,
  websiteCollaboratorsRequest
} from "../query-configs/websites"
import { getWebsiteCollaboratorsCursor } from "../selectors/websites"

import {
  WebsiteCollaborator,
  WebsiteCollaboratorFormData
} from "../types/websites"

interface MatchParams {
  username: string
  name: string
}

type Props = RouteComponentProps<Record<string, never>>

export default function SiteCollaboratorEditPanel({
  history
}: Props): JSX.Element | null {
  const match = useRouteMatch<MatchParams>()
  const { username, name } = match.params
  const [{ isPending }] = useRequest(websiteCollaboratorsRequest(name))
  const [collaboratorQueryState, updateCollaboratorRole] = useMutation(
    editWebsiteCollaboratorMutation
  )
  const collaborators = useSelector(getWebsiteCollaboratorsCursor)(name)
  const collaborator = collaborators?.find(
    (user: WebsiteCollaborator) => user.username === username
  )

  if (!collaborator) {
    return null
  }

  if (isPending) {
    return <div>Loading...</div>
  }

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
    const response = await updateCollaboratorRole(
      name,
      collaborator,
      values.role
    )
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
          role: errors["role"]
        })
      }
      return
    }
    setSubmitting(false)
    history.push(siteCollaboratorsUrl.param({ name }).toString())
  }

  return (
    <div className="narrow-page-body m-3">
      <h3>Edit role for {collaborator.name}</h3>
      <div className="form-container m-3 p-3">
        <SiteCollaboratorForm
          collaborator={collaborator}
          onSubmit={onSubmit}
        ></SiteCollaboratorForm>
      </div>
    </div>
  )
}
