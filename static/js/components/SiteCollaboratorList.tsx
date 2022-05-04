import React, { MouseEvent as ReactMouseEvent, useState } from "react"
import { useSelector } from "react-redux"
import { QueryConfig } from "redux-query"
import { useMutation, useRequest } from "redux-query-react"

import Dialog from "./Dialog"
import SiteCollaboratorDrawer from "./SiteCollaboratorDrawer"

import { EDITABLE_ROLES, ROLE_LABELS } from "../constants"
import {
  deleteWebsiteCollaboratorMutation,
  websiteCollaboratorsRequest
} from "../query-configs/websites"
import { useWebsite } from "../context/Website"
import { getWebsiteCollaboratorsCursor } from "../selectors/websites"

import { WebsiteCollaborator } from "../types/websites"
import DocumentTitle, { formatTitle } from "./DocumentTitle"
import { StudioList, StudioListItem } from "./StudioList"

export default function SiteCollaboratorList(): JSX.Element | null {
  const { name, title } = useWebsite()

  const [{ isPending }] = useRequest(websiteCollaboratorsRequest(name))
  const collaborators = useSelector(getWebsiteCollaboratorsCursor)(name)

  const [deleteModal, setDeleteModal] = useState(false)
  const [editVisibility, setEditVisibility] = useState<boolean>(false)
  const [
    selectedCollaborator,
    setSelectedCollaborator
  ] = useState<WebsiteCollaborator | null>(null)

  const closeDeleteModal = useCallback(() => setDeleteModal(false), [])
  const openDeleteModal = useCallback(() => setDeleteModal(true), [])
  const toggleEditVisibility = () => setEditVisibility(!editVisibility)

  const startEdit = (collaborator: WebsiteCollaborator | null) => (
    event: ReactMouseEvent<HTMLButtonElement>
  ) => {
    event.preventDefault()
    setSelectedCollaborator(collaborator)
    setEditVisibility(true)
  }

  const startDelete = (collaborator: WebsiteCollaborator) => (
    event: ReactMouseEvent<HTMLButtonElement>
  ) => {
    event.preventDefault()
    setSelectedCollaborator(collaborator)
    openDeleteModal()
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
      <DocumentTitle title={formatTitle(title, "Collaborators")} />
      <SiteCollaboratorDrawer
        siteName={name}
        collaborator={selectedCollaborator}
        visibility={editVisibility}
        toggleVisibility={toggleEditVisibility}
      />
      <div className="d-flex justify-content-between align-items-center py-3">
        <h2 className="m-0 p-0">Collaborators</h2>
        <button className="btn cyan-button" onClick={startEdit(null)}>
          Add collaborator
        </button>
      </div>
      <StudioList>
        {collaborators.map((collaborator: WebsiteCollaborator, i: number) => (
          <StudioListItem
            key={i}
            title={collaborator.name || collaborator.email}
            subtitle={ROLE_LABELS[collaborator.role]}
            menuOptions={
              EDITABLE_ROLES.includes(collaborator.role) ?
                [
                  ["Settings", startEdit(collaborator)],
                  ["Delete", startDelete(collaborator)]
                ] :
                []
            }
          />
        ))}
      </StudioList>
      <Dialog
        open={deleteModal}
        onCancel={closeDeleteModal}
        headerContent={"Remove collaborator"}
        bodyContent={`Are you sure you want to remove ${
          selectedCollaborator ? selectedCollaborator.name : "this user"
        }?`}
        acceptText="Delete"
        onAccept={() => {
          onDelete()
          closeDeleteModal()
        }}
      />
    </>
  )
}
