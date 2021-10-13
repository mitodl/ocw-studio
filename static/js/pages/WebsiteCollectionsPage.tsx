import React, { useCallback, useState } from "react"
import { useRequest } from "redux-query-react"
import { useSelector } from "react-redux"
import { useLocation } from "react-router-dom"

import PaginationControls from "../components/PaginationControls"
import Card from "../components/Card"
import BasicModal from "../components/BasicModal"
import WebsiteCollectionEditor from "../components/WebsiteCollectionEditor"

import { WEBSITE_CONTENT_PAGE_SIZE } from "../constants"
import {
  websiteCollectionListRequest,
  WebsiteCollectionListingResponse
} from "../query-configs/website_collections"
import { getWebsiteCollectionListingCursor } from "../selectors/website_collections"
import {
  WebsiteCollection,
  WebsiteCollectionModalState
} from "../types/website_collections"
import { collectionsBaseUrl } from "../lib/urls"
import { createModalState } from "../types/modal_state"

export default function WebsiteCollectionsPage(): JSX.Element {
  const { search } = useLocation()

  const offset = Number(new URLSearchParams(search).get("offset") ?? 0)

  const [modalState, setModalState] = useState<WebsiteCollectionModalState>(
    createModalState("closed")
  )

  const [, refresh] = useRequest(websiteCollectionListRequest(offset))

  const websiteCollectionsListingCursor = useSelector(
    getWebsiteCollectionListingCursor
  )

  const listing: WebsiteCollectionListingResponse = websiteCollectionsListingCursor(
    offset
  )

  const closeDrawer = useCallback(() => {
    refresh()
    setModalState(createModalState("closed"))
  }, [setModalState, refresh])

  const startAddingCollection = useCallback(() => {
    setModalState(createModalState("adding"))
  }, [setModalState])

  const startEditingCollection = useCallback(
    (websiteCollectionId: number) => {
      setModalState(createModalState("editing", websiteCollectionId))
    },
    [setModalState]
  )

  return (
    <>
      <BasicModal
        isVisible={!modalState.closed()}
        hideModal={closeDrawer}
        title={modalState.editing() ? "Edit" : "Add"}
        className="my-modal right"
      >
        {modalProps => (
          <div className="m-3">
            <WebsiteCollectionEditor
              modalState={modalState}
              hideModal={modalProps.hideModal}
            />
          </div>
        )}
      </BasicModal>
      <div className="px-4 dashboard">
        <div className="content">
          <div className="d-flex flex-direction-row align-items-center justify-content-between pb-3">
            <h3>Collections</h3>
            <a className="btn cyan-button add" onClick={startAddingCollection}>
              Add New
            </a>
          </div>
          <Card>
            <ul className="ruled-list">
              {listing.results.map((collection: WebsiteCollection) => (
                <li className="py-3" key={collection.id}>
                  <a
                    className="edit-collection"
                    onClick={() => startEditingCollection(collection.id)}
                  >
                    {collection.title}
                  </a>
                  <div className="text-gray">{collection.description}</div>
                </li>
              ))}
            </ul>
            <PaginationControls
              listing={listing}
              previous={collectionsBaseUrl
                .query({ offset: offset - WEBSITE_CONTENT_PAGE_SIZE })
                .toString()}
              next={collectionsBaseUrl
                .query({ offset: offset + WEBSITE_CONTENT_PAGE_SIZE })
                .toString()}
            />
          </Card>
        </div>
      </div>
    </>
  )
}
