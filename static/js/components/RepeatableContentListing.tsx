import React, {
  MouseEvent as ReactMouseEvent,
  useCallback,
  useEffect,
  useState
} from "react"
import { useLocation } from "react-router-dom"
import { useMutation, useRequest } from "redux-query-react"
import { useSelector, useStore } from "react-redux"
import { requestAsync } from "redux-query"
import useInterval from "@use-it/interval"
import { DateTime } from "luxon"
import { isNil } from "ramda"

import DriveSyncStatusIndicator from "./DriveSyncStatusIndicator"
import SiteContentEditor from "./SiteContentEditor"
import PaginationControls from "./PaginationControls"
import BasicModal from "./BasicModal"
import { useWebsite } from "../context/Website"
import useConfirmation from "../hooks/confirmation"

import {
  GOOGLE_DRIVE_SYNC_PROCESSING_STATES,
  WEBSITE_CONTENT_PAGE_SIZE
} from "../constants"
import { siteContentListingUrl } from "../lib/urls"
import { hasMainContentField } from "../lib/site_content"
import {
  syncWebsiteContentMutation,
  websiteContentListingRequest,
  WebsiteContentListingResponse,
  websiteStatusRequest
} from "../query-configs/websites"
import { getWebsiteContentListingCursor } from "../selectors/websites"

import {
  ContentListingParams,
  RepeatableConfigItem,
  WebsiteContentListItem,
  WebsiteContentModalState
} from "../types/websites"
import { createModalState } from "../types/modal_state"
import { StudioList, StudioListItem } from "./StudioList"
import ConfirmationModal from "./ConfirmationModal"

export default function RepeatableContentListing(props: {
  configItem: RepeatableConfigItem
}): JSX.Element | null {
  const store = useStore()
  const { configItem } = props
  const isResource = configItem.name === "resource"
  const website = useWebsite()

  const { search, pathname } = useLocation()
  const offset = Number(new URLSearchParams(search).get("offset") ?? 0)
  const [dirty, setDirty] = useState<boolean>(false)
  useEffect(() => {
    // make sure we clear state if we switch pages
    setDirty(false)
  }, [pathname])

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

  const closeContentDrawer = useCallback(() => {
    setDrawerState(createModalState("closed"))
  }, [setDrawerState])
  const {
    confirmationModalVisible,
    setConfirmationModalVisible,
    conditionalClose
  } = useConfirmation({ dirty, setDirty, close: closeContentDrawer })

  useInterval(
    async () => {
      if (
        SETTINGS.gdrive_enabled &&
        isResource &&
        website &&
        (isNil(website.gdrive_url) ||
          (website.sync_status &&
            GOOGLE_DRIVE_SYNC_PROCESSING_STATES.includes(
              // @ts-ignore
              website.sync_status
            )))
      ) {
        const response = await store.dispatch(
          // This will update the DriveSyncStatusIndicator
          requestAsync(websiteStatusRequest(website.name))
        )
        if (
          response.body.sync_status &&
          !GOOGLE_DRIVE_SYNC_PROCESSING_STATES.includes(
            response.body.sync_status
          )
        ) {
          // This will update the content listing
          await store.dispatch(
            requestAsync(
              websiteContentListingRequest(listingParams, false, false)
            )
          )
        }
      }
    },
    website ? 5000 : null
  )

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
    await syncWebsiteContent()
    await store.dispatch(requestAsync(websiteStatusRequest(website.name)))
  }

  // @ts-ignore
  return (
    <>
      <ConfirmationModal
        dirty={dirty}
        confirmationModalVisible={confirmationModalVisible}
        setConfirmationModalVisible={setConfirmationModalVisible}
        dismiss={() => conditionalClose(true)}
      />
      <BasicModal
        isVisible={drawerState.open()}
        hideModal={() => conditionalClose(false)}
        title={modalTitle}
        className={modalClassName}
      >
        {() =>
          drawerState.open() ? (
            <div className="m-2">
              <SiteContentEditor
                loadContent={true}
                configItem={configItem}
                editorState={drawerState}
                dismiss={() => conditionalClose(true)}
                fetchWebsiteContentListing={fetchWebsiteContentListing}
                setDirty={setDirty}
              />
            </div>
          ) : null
        }
      </BasicModal>
      <div className="d-flex flex-direction-row align-items-right justify-content-between py-3">
        <h2 className="m-0 p-0">{configItem.label}</h2>
        <div className="noflex">
          {SETTINGS.gdrive_enabled && isResource ? (
            website.gdrive_url ? (
              <>
                <div>
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
                </div>
                <DriveSyncStatusIndicator website={website} />
              </>
            ) : null
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
      <StudioList>
        {listing.results.map((item: WebsiteContentListItem) => (
          <StudioListItem
            key={item.text_id}
            onClick={startAddOrEdit(item.text_id)}
            title={item.title ?? ""}
            subtitle={`Updated ${DateTime.fromISO(
              item.updated_on
            ).toRelative()}`}
          />
        ))}
      </StudioList>
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
