import React, { useState } from "react"
import { useRouteMatch, Link } from "react-router-dom"
import { useSelector } from "react-redux"
import { QueryConfig } from "redux-query"
import { useMutation, useRequest } from "redux-query-react"

import Dialog from "./Dialog"
import Card from "./Card"

import { EDITABLE_ROLES, ROLE_LABELS } from "../constants"
import {
  siteCollaboratorsAddUrl,
  siteCollaboratorsDetailUrl
} from "../lib/urls"
import {
  deleteWebsiteCollaboratorMutation,
  websiteCollaboratorsRequest
} from "../query-configs/websites"
import { getWebsiteCollaboratorsCursor } from "../selectors/websites"

import { WebsiteCollaborator } from "../types/websites"

interface MatchParams {
  name: string
}

export default function SiteCollaboratorList(): JSX.Element | null {
  const match = useRouteMatch<MatchParams>()
  const { name } = match.params

  const [{ isPending }] = useRequest(websiteCollaboratorsRequest(name))
  const collaborators = useSelector(getWebsiteCollaboratorsCursor)(name)

  const [deleteModal, setDeleteModal] = useState(false)
  const [selectedCollaborator, setSelectedCollaborator] = useState<
    WebsiteCollaborator | undefined
  >()

  const toggleDeleteModal = () => setDeleteModal(!deleteModal)

  const [deleteQueryState, deleteCollaborator] = useMutation(
    (): QueryConfig => {
      // @ts-ignore
      return deleteWebsiteCollaboratorMutation(name, selectedCollaborator)
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
    <div className="collaborator-list">
      <Card>
        <div className="d-flex justify-content-between align-items-center pb-3">
          <h3>Collaborators</h3>
          <Link
            className="collaborator-add-btn btn blue-button"
            to={siteCollaboratorsAddUrl.param({ name }).toString()}
          >
            Add collaborator
          </Link>
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
                          <Link
                            className="edit-link"
                            to={siteCollaboratorsDetailUrl
                              .param({
                                name,
                                username: collaborator.username
                              })
                              .toString()}
                          >
                            <i className="material-icons">edit</i>
                          </Link>
                          <i
                            className="material-icons"
                            onClick={() => {
                              setSelectedCollaborator(collaborator)
                              toggleDeleteModal()
                            }}
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
  )
}
