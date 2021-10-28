import React, {
  MouseEvent as ReactMouseEvent,
  useCallback,
  useState
} from "react"
import { useLocation } from "react-router-dom"
import { useMutation, useRequest } from "redux-query-react"
import { useSelector } from "react-redux"

import SiteContentEditor from "./SiteContentEditor"
import PaginationControls from "./PaginationControls"
import Card from "./Card"
import BasicModal from "./BasicModal"
import { useWebsite } from "../context/Website"

import { WEBSITE_CONTENT_PAGE_SIZE } from "../constants"
import { siteContentListingUrl } from "../lib/urls"
import { hasMainContentField } from "../lib/site_content"
import {
  syncWebsiteContentMutation,
  websiteContentListingRequest,
  WebsiteContentListingResponse
} from "../query-configs/websites"
import { getWebsiteContentListingCursor } from "../selectors/websites"

import {
  ContentListingParams,
  RepeatableConfigItem,
  WebsiteContentListItem,
  WebsiteContentModalState
} from "../types/websites"
import { createModalState } from "../types/modal_state"

export default function RepeatableContentListing(props: {
  configItem: RepeatableConfigItem
}): JSX.Element | null {
  const { configItem } = props

  const website = useWebsite()

  const { search } = useLocation()
  const offset = Number(new URLSearchParams(search).get("offset") ?? 0)

  const listingParams: ContentListingParams = {
    name: website.name,
    type: configItem.name,
    offset
  }
  const [
    { isPending: contentListingPending },
    fetchWebsiteContentListing
  ] = useRequest(websiteContentListingRequest(listingParams, false, false))
  const listing: WebsiteContentListingResponse = useSelector(
    getWebsiteContentListingCursor
  )(listingParams)
  const [{ isPending: syncIsPending }, syncWebsiteContent] = useMutation(() =>
    syncWebsiteContentMutation(website.name)
  )

  const [drawerState, setDrawerState] = useState<WebsiteContentModalState>(
    createModalState("closed")
  )
  const [syncModalState, setSyncModalState] = useState({
    message:   "",
    isVisible: false
  })
  const toggleSyncModal = (message: string) =>
    setSyncModalState({
      message:   message,
      isVisible: !syncModalState.isVisible
    })

  const closeContentDrawer = useCallback(() => {
    setDrawerState(createModalState("closed"))
  }, [setDrawerState])

  if (contentListingPending) {
    return <div className="site-page container">Loading...</div>
  }
  if (!listing) {
    return null
  }

  const startAddOrEdit = (textId: string | null) => (
    event: ReactMouseEvent<HTMLLIElement | HTMLButtonElement, MouseEvent>
  ) => {
    event.preventDefault()

    setDrawerState(
      textId ? createModalState("editing", textId) : createModalState("adding")
    )
  }

  const labelSingular = configItem.label_singular ?? configItem.label

  const modalTitle = `${
    drawerState.editing() ? "Edit" : "Add"
  } ${labelSingular}`

  const modalClassName = `right ${
    hasMainContentField(configItem.fields) ? "wide" : ""
  }`

  const onSubmitContentSync = async (
    event: ReactMouseEvent<HTMLLIElement | HTMLButtonElement, MouseEvent>
  ) => {
    event.preventDefault()
    if (syncIsPending) {
      return
    }
    const response = await syncWebsiteContent()
    const successMsg =
      "Resources are being synced with Google Drive. Please revisit this page in a few minutes."
    const failMsg =
      "Something went wrong syncing with Google Drive.  Please try again or contact support."
    toggleSyncModal(!response || response.status !== 200 ? failMsg : successMsg)
  }

  return (
    <>
      <BasicModal
        isVisible={drawerState.open()}
        hideModal={closeContentDrawer}
        title={modalTitle}
        className={modalClassName}
      >
        {modalProps =>
          drawerState.open() ? (
            <div className="m-2">
              <SiteContentEditor
                loadContent={true}
                configItem={configItem}
                editorState={drawerState}
                hideModal={modalProps.hideModal}
                fetchWebsiteContentListing={fetchWebsiteContentListing}
              />
            </div>
          ) : null
        }
      </BasicModal>
      <BasicModal
        isVisible={syncModalState.isVisible}
        hideModal={() => toggleSyncModal("")}
        title="Syncing with Google Drive"
        className={null}
      >
        {_ =>
          syncModalState ? (
            <div className="m-2">{syncModalState.message}</div>
          ) : null
        }
      </BasicModal>
      <div className="d-flex flex-direction-row align-items-right justify-content-between py-3">
        <h2 className="m-0 p-0">{configItem.label}</h2>
        <div className="noflex">
          {SETTINGS.gdrive_enabled && configItem.name === "resource" ? (
            <>
              <button
                className="btn cyan-button sync ml-2"
                onClick={onSubmitContentSync}
              >
                Sync w/Google Drive
              </button>
              <a
                className="view"
                target="_blank"
                rel="noopener noreferrer"
                href={website.gdrive_url}
              >
                <i className="material-icons gdrive-link">open_in_new</i>
              </a>
            </>
          ) : (
            <button
              className="btn cyan-button add"
              onClick={startAddOrEdit(null)}
            >
              Add {labelSingular}
            </button>
          )}
        </div>
      </div>
      <Card>
        <ul className="ruled-list">
          {listing.results.map((item: WebsiteContentListItem) => (
            <li
              key={item.text_id}
              className="py-3 listing-result"
              onClick={startAddOrEdit(item.text_id)}
            >
              <div className="d-flex flex-direction-row align-items-center justify-content-between">
                <span>{item.title}</span>
              </div>
            </li>
          ))}
        </ul>
      </Card>
      <PaginationControls
        listing={listing}
        previous={siteContentListingUrl
          .param({
            name:        website.name,
            contentType: configItem.name
          })
          .query({ offset: offset - WEBSITE_CONTENT_PAGE_SIZE })
          .toString()}
        next={siteContentListingUrl
          .param({
            name:        website.name,
            contentType: configItem.name
          })
          .query({ offset: offset + WEBSITE_CONTENT_PAGE_SIZE })
          .toString()}
      />
    </>
  )
}
