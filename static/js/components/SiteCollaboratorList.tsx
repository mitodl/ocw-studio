import React, { MouseEvent as ReactMouseEvent, useState } from "react"
import { useRouteMatch } from "react-router-dom"
import { useSelector } from "react-redux"
import { QueryConfig } from "redux-query"
import { useMutation, useRequest } from "redux-query-react"

import Dialog from "./Dialog"
import Card from "./Card"

import { EDITABLE_ROLES, ROLE_LABELS } from "../constants"
import {
  deleteWebsiteCollaboratorMutation,
  websiteCollaboratorsRequest
} from "../query-configs/websites"
import { getWebsiteCollaboratorsCursor } from "../selectors/websites"

import { WebsiteCollaborator } from "../types/websites"
import SiteCollaboratorDrawer from "./SiteCollaboratorDrawer"

interface MatchParams {
  name: string
}

export default function SiteCollaboratorList(): JSX.Element | null {
  const match = useRouteMatch<MatchParams>()
  const { name } = match.params

  const [{ isPending }] = useRequest(websiteCollaboratorsRequest(name))
  const collaborators = useSelector(getWebsiteCollaboratorsCursor)(name)

  const [deleteModal, setDeleteModal] = useState(false)
  const [editVisibility, setEditVisibility] = useState<boolean>(false)
  const [
    selectedCollaborator,
    setSelectedCollaborator
  ] = useState<WebsiteCollaborator | null>(null)

  const toggleDeleteModal = () => setDeleteModal(!deleteModal)
  const toggleEditVisibility = () => setEditVisibility(!editVisibility)

  const startEdit = (collaborator: WebsiteCollaborator | null) => (
    event: ReactMouseEvent<HTMLAnchorElement, MouseEvent>
  ) => {
    event.preventDefault()
    setSelectedCollaborator(collaborator)
    setEditVisibility(true)
  }

  const startDelete = (collaborator: WebsiteCollaborator) => (
    event: ReactMouseEvent<HTMLAnchorElement, MouseEvent>
  ) => {
    event.preventDefault()
    setSelectedCollaborator(collaborator)
    toggleDeleteModal()
  }

  const [deleteQueryState, deleteCollaborator] = useMutation(
    (): QueryConfig => {
      return deleteWebsiteCollaboratorMutation(
        name,
        selectedCollaborator as WebsiteCollaborator
      )
    }
  )

  const onDelete = async () => {
    if (deleteQueryState.isPending) {
      return
    }
    const response = await deleteCollaborator()
    if (!response) {
      return
    }
  }

  if (!collaborators) {
    return null
  }

  if (isPending) {
    return <div>Loading...</div>
  }

  return (
    <>
      <SiteCollaboratorDrawer
        siteName={name}
        collaborator={selectedCollaborator}
        visibility={editVisibility}
        toggleVisibility={toggleEditVisibility}
      />
      <div className="collaborator-list">
        <Card>
          <div className="d-flex justify-content-between align-items-center pb-3">
            <h3>Collaborators</h3>
            <a
              className="collaborator-add-btn btn blue-button"
              onClick={startEdit(null)}
            >
              Add collaborator
            </a>
          </div>
          <div className="narrow-page-body pb-5">
            <table className="table collaborator-table">
              <tbody>
                {collaborators.map(
                  (collaborator: WebsiteCollaborator, i: number) => (
                    <tr key={i}>
                      <td className="pr-5">
                        {collaborator.name || collaborator.email}
                      </td>
                      <td className="pr-5 gray">
                        {ROLE_LABELS[collaborator.role]}&nbsp;
                      </td>
                      <td className="gray">
                        {EDITABLE_ROLES.includes(collaborator.role) ? (
                          <>
                            <a
                              className="edit-link"
                              onClick={startEdit(collaborator)}
                            >
                              <i className="material-icons">edit</i>
                            </a>
                            <i
                              className="material-icons"
                              onClick={startDelete(collaborator)}
                            >
                              delete_outline
                            </i>
                          </>
                        ) : null}
                      </td>
                    </tr>
                  )
                )}
              </tbody>
            </table>
          </div>
        </Card>
        <Dialog
          open={deleteModal}
          toggleModal={toggleDeleteModal}
          headerContent={"Remove collaborator"}
          bodyContent={`Are you sure you want to remove ${
            selectedCollaborator ? selectedCollaborator.name : "this user"
          }?`}
          acceptText="Delete"
          onAccept={() => {
            onDelete()
            toggleDeleteModal()
          }}
        ></Dialog>
      </div>
    </>
  )
}
