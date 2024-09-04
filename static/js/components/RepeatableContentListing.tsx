import React, {
  MouseEvent as ReactMouseEvent,
  useCallback,
  useState,
  useEffect,
} from "react"
import { Link, Route, useLocation } from "react-router-dom"
import { useMutation, useRequest } from "redux-query-react"
import { useSelector, useStore } from "react-redux"
import { QueryConfig, requestAsync } from "redux-query"
import useInterval from "@use-it/interval"
import { isNil } from "ramda"

import DriveSyncStatusIndicator from "./DriveSyncStatusIndicator"
import PaginationControls from "./PaginationControls"

import { GOOGLE_DRIVE_SYNC_PROCESSING_STATES } from "../constants"
import { siteContentDetailUrl, siteContentNewUrl } from "../lib/urls"
import { addDefaultFields } from "../lib/site_content"
import {
  syncWebsiteContentMutation,
  websiteContentListingRequest,
  WebsiteContentListingResponse,
  websiteStatusRequest,
  deleteWebsiteContentMutation,
} from "../query-configs/websites"
import { getWebsiteContentListingCursor } from "../selectors/websites"

import {
  ContentListingParams,
  RepeatableConfigItem,
  WebsiteContentListItem,
} from "../types/websites"
import { StudioList, StudioListItem } from "./StudioList"
import { useURLParamFilter, usePagination } from "../hooks/search"
import { singular } from "pluralize"
import SiteContentEditorDrawer from "./SiteContentEditorDrawer"
import { useWebsite } from "../context/Website"
import { formatUpdatedOn } from "../util/websites"
import Dialog from "./Dialog"
import posthog from "posthog-js"

export default function RepeatableContentListing(props: {
  configItem: RepeatableConfigItem
}): JSX.Element | null {
  const store = useStore()
  const { configItem } = props
  const isResource = configItem.name === "resource"

  const website = useWebsite()

  const [isContentDeletable, setIsContentDeletable] = useState(false)

  useEffect(() => {
    const checkFeatureFlag = async () => {
      const flagEnabled =
        (await posthog.isFeatureEnabled("OCW_STUDIO_CONTENT_DELETABLE")) ??
        false
      setIsContentDeletable(flagEnabled)
    }
    checkFeatureFlag()
  }, [])

  const isDeletable =
    isContentDeletable &&
    ["external-resource", "instructor"].includes(configItem.name)

  const getListingParams = useCallback(
    (search: string): ContentListingParams => {
      const qsParams = new URLSearchParams(search)
      const offset = Number(qsParams.get("offset") ?? 0)
      const searchString = qsParams.get("q")

      const params: ContentListingParams = {
        name: website.name,
        type: configItem.name,
        offset,
      }
      if (searchString) {
        params.search = searchString
      }
      return params
    },
    [website, configItem],
  )

  const { listingParams, searchInput, setSearchInput } =
    useURLParamFilter(getListingParams)

  const [, fetchWebsiteContentListing] = useRequest(
    websiteContentListingRequest(listingParams, false, false),
  )

  const listing: WebsiteContentListingResponse = useSelector(
    getWebsiteContentListingCursor,
  )(listingParams)

  const [{ isPending: syncIsPending }, syncWebsiteContent] = useMutation(() =>
    syncWebsiteContentMutation(website.name),
  )

  useInterval(
    async () => {
      if (
        SETTINGS.gdrive_enabled &&
        isResource &&
        website &&
        (isNil(website.gdrive_url) ||
          (website.sync_status &&
            GOOGLE_DRIVE_SYNC_PROCESSING_STATES.includes(website.sync_status)))
      ) {
        const response = await store.dispatch(
          // This will update the DriveSyncStatusIndicator
          requestAsync(websiteStatusRequest(website.name)),
        )
        if (
          response.body.sync_status &&
          !GOOGLE_DRIVE_SYNC_PROCESSING_STATES.includes(
            response.body.sync_status,
          )
        ) {
          // This will update the content listing
          await store.dispatch(
            requestAsync(
              websiteContentListingRequest(listingParams, false, false),
            ),
          )
        }
      }
    },
    website ? 5000 : null,
  )

  const labelSingular = configItem.label_singular ?? singular(configItem.label)

  const onSubmitContentSync = async (
    event: ReactMouseEvent<HTMLLIElement | HTMLButtonElement, MouseEvent>,
  ) => {
    event.preventDefault()
    if (syncIsPending) {
      return
    }
    await syncWebsiteContent()
    await store.dispatch(requestAsync(websiteStatusRequest(website.name)))
  }

  const { search } = useLocation()
  const searchParams = new URLSearchParams(search)

  const pages = usePagination(listing.count ?? 0)

  const [deleteModal, setDeleteModal] = useState(false)
  const [selectedContent, setSelectedContent] =
    useState<WebsiteContentListItem | null>(null)

  const closeDeleteModal = useCallback(() => setDeleteModal(false), [])
  const openDeleteModal = useCallback(() => setDeleteModal(true), [])

  const startDelete =
    (content: WebsiteContentListItem) =>
    (event: ReactMouseEvent<HTMLButtonElement>) => {
      event.preventDefault()
      setSelectedContent(content)
      openDeleteModal()
    }

  const [deleteQueryState, deleteContent] = useMutation((): QueryConfig => {
    return deleteWebsiteContentMutation(
      website.name,
      selectedContent?.text_id as string,
    )
  })

  const onDelete = async () => {
    if (deleteQueryState.isPending) {
      return
    }
    const response = await deleteContent()
    if (!response) {
      return
    } else if (fetchWebsiteContentListing) {
      fetchWebsiteContentListing()
      await store.dispatch(requestAsync(websiteStatusRequest(website.name)))
    }
  }

  return (
    <>
      <div className="d-flex flex-direction-row align-items-center justify-content-between py-3">
        <h2 className="m-0 p-0">{configItem.label}</h2>
        <div className="d-flex flex-direction-row align-items-top">
          <input
            placeholder={`Search for a ${labelSingular}`}
            className="site-search-input mr-3 form-control"
            value={searchInput}
            onChange={setSearchInput}
          />
          {SETTINGS.gdrive_enabled && isResource ? (
            website.gdrive_url ? (
              <div className="d-flex flex-column">
                <div className="d-flex">
                  <button
                    className="btn cyan-button sync ml-2 text-nowrap"
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
              </div>
            ) : null
          ) : (
            <Link
              className="btn cyan-button add flex-shrink-0"
              to={siteContentNewUrl
                .param({
                  name: website.name,
                  contentType: configItem.name,
                })
                .query(searchParams)
                .toString()}
            >
              Add {labelSingular}
            </Link>
          )}
        </div>
      </div>
      <StudioList>
        {listing.results.map((item: WebsiteContentListItem) => (
          <StudioListItem
            key={item.text_id}
            to={siteContentDetailUrl
              .param({
                name: website.name,
                contentType: configItem.name,
                uuid: item.text_id,
              })
              .toString()}
            title={item.title ?? ""}
            subtitle={`Updated ${formatUpdatedOn(item)}`}
            menuOptions={
              isDeletable ? [["Delete", startDelete(item)]] : undefined
            }
          />
        ))}
      </StudioList>
      <PaginationControls previous={pages.previous} next={pages.next} />
      <Route
        path={[
          siteContentDetailUrl.param({
            name: website.name,
          }).pathname,
          siteContentNewUrl.param({
            name: website.name,
          }).pathname,
        ]}
      >
        <SiteContentEditorDrawer
          configItem={addDefaultFields(configItem)}
          fetchWebsiteContentListing={fetchWebsiteContentListing}
        />
      </Route>
      <Dialog
        open={deleteModal}
        onCancel={closeDeleteModal}
        headerContent={`Remove ${labelSingular}`}
        bodyContent={`Are you sure you want to remove ${
          selectedContent && selectedContent.title
            ? selectedContent.title
            : "this content"
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
