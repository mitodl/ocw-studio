import React, { useState } from "react"
import { RouteComponentProps, useRouteMatch } from "react-router-dom"
import { useSelector } from "react-redux"
import { QueryConfig } from "redux-query"
import { useMutation, useRequest } from "redux-query-react"

import Dialog from "./Dialog"
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

type Props = RouteComponentProps<Record<string, never>>

export default function SiteCollaboratorList({
  history
}: Props): JSX.Element | null {
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
    <div>
      <h3>Collaborators</h3>
      <div className="collaborator-add-btn">
        <button
          type="submit"
          onClick={() => history.push(siteCollaboratorsAddUrl(name))}
        >
          Add collaborator
        </button>
      </div>
      <div className="narrow-page-body pb-5">
        <table className="table table-striped collaborator-table">
          <tbody>
            {collaborators.map(
              (collaborator: WebsiteCollaborator, i: number) => (
                <tr key={i}>
                  <td className="pr-5">
                    {collaborator.name || collaborator.email}
                  </td>
                  <td className="pr-5">
                    {ROLE_LABELS[collaborator.role]}&nbsp;
                  </td>
                  <td>
                    {EDITABLE_ROLES.includes(collaborator.role) ? (
                      <>
                        <i
                          className="material-icons"
                          onClick={() =>
                            history.push(
                              siteCollaboratorsDetailUrl(
                                name,
                                collaborator.username
                              )
                            )
                          }
                        >
                          edit
                        </i>
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
