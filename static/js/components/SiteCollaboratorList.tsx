import React, {
  MouseEvent as ReactMouseEvent,
  useCallback,
  useState,
} from "react"
import { useSelector, useStore } from "react-redux"
import { QueryConfig } from "redux-query"
import { useMutation, useRequest } from "redux-query-react"

import Dialog from "./Dialog"
import SiteCollaboratorDrawer from "./SiteCollaboratorDrawer"

import { EDITABLE_ROLES, ROLE_LABELS } from "../constants"
import {
  WebsiteCollaboratorListingResponse,
  deleteWebsiteCollaboratorMutation,
  websiteCollaboratorListingRequest,
  websiteCollaboratorsRequest
} from "../query-configs/websites"
import { useWebsite } from "../context/Website"
import { getWebsiteCollaboratorListingCursor, getWebsiteCollaboratorsCursor, getWebsiteContentListingCursor } from "../selectors/websites"

import { CollaboratorListingParams, WebsiteCollaborator, WebsiteCollaboratorListItem } from "../types/websites"
import DocumentTitle, { formatTitle } from "./DocumentTitle"
import { StudioList, StudioListItem } from "./StudioList"
import { usePagination, useURLParamFilter } from "../hooks/search"
import { formatUpdatedOn } from "../util/websites"
import PaginationControls from "./PaginationControls"

export default function SiteCollaboratorList(): JSX.Element | null {
  const store = useStore()
  const website = useWebsite()
  const { name, title } = website

  console.log(name, title)

  const getListingParams = useCallback(
    (search: string): CollaboratorListingParams => {
      const qsParams = new URLSearchParams(search)
      const offset = Number(qsParams.get("offset") ?? 0)

      const params: CollaboratorListingParams = {
        name: website.name,
        offset
      }
      return params
    },
    [website]
  )

  const { listingParams, searchInput, setSearchInput } =
  useURLParamFilter(getListingParams)

  console.log("listing params",listingParams)

const [, fetchWebsiteCollaboratorListing] = useRequest(
  websiteCollaboratorListingRequest(listingParams, false, false)
)
// console.log("fetch",  websiteCollaboratorListingRequest(listingParams, false, false))

const listing: WebsiteCollaboratorListingResponse = useSelector(
  getWebsiteCollaboratorListingCursor
)(listingParams)

console.log("listing", listing, listing.count)
  // const [{ isPending }] = useRequest(websiteCollaboratorsRequest(name))
  // const collaborators = useSelector(getWebsiteCollaboratorsCursor)(name)
  // console.log("collaborators", collaborators)

  // console.log("use request", useRequest(websiteCollaboratorsRequest(name)))
  // console.log("collaborators", useSelector(getWebsiteCollaboratorsCursor)(name))
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
    }
  }

  const pages = usePagination(listing.count ?? 0)
  // if (!collaborators) {
  //   return null
  // }

  // if (isPending) {
  //   return <div>Loading...</div>
  // }

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
      {/* <StudioList>
        {listing.map((collaborator: WebsiteCollaborator, i: number) => (
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
      </StudioList> */}
      <StudioList>
        {listing.results.map((item: WebsiteCollaboratorListItem, i:number) => (
          <StudioListItem
            key={i}
            title={(item.name ?? "") || (item.email ?? "") }
            subtitle={ROLE_LABELS[item.role]}
            // menuOptions={
            //   EDITABLE_ROLES.includes(item.role) ?
            //     [
            //       ["Settings", startEdit(item)],
            //       ["Delete", startDelete(item)]
            //     ] :
            //     []
            // }
            // subtitle={`Updated now`}
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
