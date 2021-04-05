import React from "react"
import { useMutation } from "redux-query-react"
import { FormikHelpers } from "formik"
import { is } from "ramda"

import Card from "./Card"
import SiteCollaboratorForm from "./forms/SiteCollaboratorForm"
import { getResponseBodyError, isErrorResponse } from "../lib/util"
import {
  createWebsiteCollaboratorMutation,
  editWebsiteCollaboratorMutation
} from "../query-configs/websites"

import {
  WebsiteCollaborator,
  WebsiteCollaboratorFormData
} from "../types/websites"
import { Modal, ModalBody, ModalHeader } from "reactstrap"

interface Props {
  collaborator: WebsiteCollaborator | null
  visibility: boolean
  toggleVisibility: () => void
  siteName: string
}

export default function SiteCollaboratorDrawer(
  props: Props
): JSX.Element | null {
  const { siteName, collaborator, visibility, toggleVisibility } = props

  const [collaboratorAddQueryState, addCollaborator] = useMutation(
    createWebsiteCollaboratorMutation
  )

  const [collaboratorEditQueryState, updateCollaboratorRole] = useMutation(
    editWebsiteCollaboratorMutation
  )

  const onSubmit = async (
    values: WebsiteCollaboratorFormData,
    {
      setSubmitting,
      setErrors,
      setStatus
    }: FormikHelpers<WebsiteCollaboratorFormData>
  ) => {
    if (
      collaboratorAddQueryState.isPending ||
      collaboratorEditQueryState.isPending
    ) {
      return
    }

    const response = await (collaborator ?
      updateCollaboratorRole(siteName, collaborator, values.role) :
      addCollaborator(siteName, values))

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
        const roleError = { role: errors["role"] }
        const emailError = collaborator ? {} : { email: errors["email"] }
        setErrors({
          ...roleError,
          ...emailError
        })
      }
      return
    }
    setSubmitting(false)
    toggleVisibility()
  }

  return (
    <div>
      <Modal
        isOpen={visibility}
        toggle={toggleVisibility}
        modalClassName="right"
      >
        <ModalHeader toggle={toggleVisibility}>
          {collaborator ? `Edit ${collaborator.email}` : "Add collaborator"}
        </ModalHeader>
        <ModalBody>
          <Card>
            <div className="form-container m-3 p-3">
              <SiteCollaboratorForm
                collaborator={collaborator}
                onSubmit={onSubmit}
              ></SiteCollaboratorForm>
            </div>
          </Card>
        </ModalBody>
      </Modal>
    </div>
  )
}
