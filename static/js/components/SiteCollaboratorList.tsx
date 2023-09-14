import React, {
  MouseEvent as ReactMouseEvent,
  useCallback,
  useState,
} from "react"
import { useSelector } from "react-redux"
import { QueryConfig } from "redux-query"
import { useMutation, useRequest } from "redux-query-react"

import Dialog from "./Dialog"
import SiteCollaboratorDrawer from "./SiteCollaboratorDrawer"

import { EDITABLE_ROLES, ROLE_LABELS } from "../constants"
import {
  WebsiteCollaboratorListingResponse,
  deleteWebsiteCollaboratorMutation,
  websiteCollaboratorListingRequest,
} from "../query-configs/websites"
import { useWebsite } from "../context/Website"
import { getWebsiteCollaboratorListingCursor } from "../selectors/websites"

import {
  CollaboratorListingParams,
  WebsiteCollaborator,
} from "../types/websites"
import DocumentTitle, { formatTitle } from "./DocumentTitle"
import { StudioList, StudioListItem } from "./StudioList"
import { usePagination, useURLParamFilter } from "../hooks/search"
import PaginationControls from "./PaginationControls"

export default function SiteCollaboratorList(): JSX.Element | null {
  const website = useWebsite()
  const { name, title } = website

  const getListingParams = useCallback(
    (search: string): CollaboratorListingParams => {
      const qsParams = new URLSearchParams(search)
      const offset = Number(qsParams.get("offset") ?? 0)

      const params: CollaboratorListingParams = {
        name: website.name,
        offset,
      }
      return params
    },
    [website],
  )

  const { listingParams } = useURLParamFilter(getListingParams)

  const [, fetchWebsiteCollaboratorListing] = useRequest(
    websiteCollaboratorListingRequest(listingParams, false, false),
  )

  const listing: WebsiteCollaboratorListingResponse = useSelector(
    getWebsiteCollaboratorListingCursor,
  )(listingParams)

  const [deleteModal, setDeleteModal] = useState(false)
  const [editVisibility, setEditVisibility] = useState<boolean>(false)
  const [selectedCollaborator, setSelectedCollaborator] =
    useState<WebsiteCollaborator | null>(null)

  const closeDeleteModal = useCallback(() => setDeleteModal(false), [])
  const openDeleteModal = useCallback(() => setDeleteModal(true), [])
  const toggleEditVisibility = () => setEditVisibility(!editVisibility)

  const startEdit =
    (collaborator: WebsiteCollaborator | null) =>
    (event: ReactMouseEvent<HTMLButtonElement>) => {
      event.preventDefault()
      setSelectedCollaborator(collaborator)
      setEditVisibility(true)
    }

  const startDelete =
    (collaborator: WebsiteCollaborator) =>
    (event: ReactMouseEvent<HTMLButtonElement>) => {
      event.preventDefault()
      setSelectedCollaborator(collaborator)
      openDeleteModal()
    }

  const [deleteQueryState, deleteCollaborator] = useMutation(
    (): QueryConfig => {
      return deleteWebsiteCollaboratorMutation(
        name,
        selectedCollaborator as WebsiteCollaborator,
      )
    },
  )

  const onDelete = async () => {
    if (deleteQueryState.isPending) {
      return
    }
    const response = await deleteCollaborator()
    if (!response) {
      return
    } else if (fetchWebsiteCollaboratorListing) {
      fetchWebsiteCollaboratorListing()
    }
  }

  const pages = usePagination(listing.count ?? 0)

  return (
    <>
      <DocumentTitle title={formatTitle(title, "Collaborators")} />
      <SiteCollaboratorDrawer
        siteName={name}
        collaborator={selectedCollaborator}
        visibility={editVisibility}
        toggleVisibility={toggleEditVisibility}
        fetchWebsiteCollaboratorListing={fetchWebsiteCollaboratorListing}
      />
      <div className="d-flex justify-content-between align-items-center py-3">
        <h2 className="m-0 p-0">Collaborators</h2>
        <button className="btn cyan-button" onClick={startEdit(null)}>
          Add collaborator
        </button>
      </div>
      <StudioList>
        {listing.results.map((collaborator: WebsiteCollaborator, i: number) => (
          <StudioListItem
            key={i}
            title={collaborator.name || collaborator.email}
            subtitle={ROLE_LABELS[collaborator.role]}
            menuOptions={
              EDITABLE_ROLES.includes(collaborator.role)
                ? [
                    ["Settings", startEdit(collaborator)],
                    ["Delete", startDelete(collaborator)],
                  ]
                : []
            }
          />
        ))}
      </StudioList>
      <PaginationControls previous={pages.previous} next={pages.next} />
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
