import React, {
  MouseEvent as ReactMouseEvent,
  useState,
  useCallback
} from "react"
import { useLocation, useRouteMatch } from "react-router-dom"
import { useRequest } from "redux-query-react"
import { useSelector } from "react-redux"
import { curry } from "ramda"

import SiteContentEditor from "./SiteContentEditor"
import PaginationControls from "./PaginationControls"
import Card from "./Card"

import { WEBSITE_CONTENT_PAGE_SIZE } from "../constants"
import { siteContentListingUrl } from "../lib/urls"
import { isRepeatableCollectionItem } from "../lib/site_content"
import {
  websiteContentListingRequest,
  WebsiteContentListingResponse
} from "../query-configs/websites"
import {
  getWebsiteContentListingCursor,
  getWebsiteDetailCursor
} from "../selectors/websites"

import {
  ContentListingParams,
  RepeatableConfigItem,
  SingletonsConfigItem,
  TopLevelConfigItem,
  WebsiteContentListItem
} from "../types/websites"
import { ContentFormType } from "../types/forms"

interface MatchParams {
  contenttype: string
  name: string
}

interface ListingComponentParams {
  listing: WebsiteContentListingResponse
  startAdd: (event: ReactMouseEvent<HTMLAnchorElement, MouseEvent>) => void
  startEdit: (
    uuid: string
  ) => (event: ReactMouseEvent<HTMLLIElement, MouseEvent>) => void
}

enum PanelVisibilityState {
  Add = "add",
  Edit = "edit",
  None = "none"
}

export function SingletonContentListing(
  props: ListingComponentParams & {
    configItem: SingletonsConfigItem
  }
): JSX.Element | null {
  const { configItem } = props

  if (configItem.files.length === 0) {
    return null
  }

  return (
    <div>
      <Card>
        <div className="d-flex flex-direction-row align-items-center justify-content-between pb-3">
          <h3>{configItem.label}</h3>
        </div>
        <ul className="ruled-list">
          {configItem.files.map((fileConfigItem, i) => (
            <li key={i} className="py-3">
              <div className="d-flex flex-direction-row align-items-center justify-content-between">
                <span>{fileConfigItem.label}</span>
              </div>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  )
}

export function RepeatableContentListing(
  props: ListingComponentParams & { configItem: RepeatableConfigItem }
): JSX.Element | null {
  const { configItem, listing, startEdit, startAdd } = props

  return (
    <div>
      <Card>
        <div className="d-flex flex-direction-row align-items-center justify-content-between pb-3">
          <h3>{configItem.label}</h3>
          <a className="btn blue-button add" onClick={startAdd}>
            Add {configItem.label}
          </a>
        </div>
        <ul className="ruled-list">
          {listing.results.map((item: WebsiteContentListItem) => (
            <li
              key={item.uuid}
              className="py-3 listing-result"
              onClick={startEdit(item.uuid)}
            >
              <div className="d-flex flex-direction-row align-items-center justify-content-between">
                <span>{item.title}</span>
              </div>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  )
}

export default function SiteContentListing(): JSX.Element | null {
  const match = useRouteMatch<MatchParams>()
  const { search } = useLocation()
  const offset = Number(new URLSearchParams(search).get("offset") ?? 0)
  const { contenttype, name } = match.params

  const website = useSelector(getWebsiteDetailCursor)(name)
  const listingParams: ContentListingParams = {
    name,
    type: contenttype,
    offset
  }

  const [
    { isPending: contentListingPending },
    runWebsiteContentListingRequest
  ] = useRequest(websiteContentListingRequest(listingParams))
  const listing: WebsiteContentListingResponse = useSelector(
    getWebsiteContentListingCursor
  )(listingParams)

  const [editItemUUID, setEditItemUUID] = useState<string | null>(null)

  const [panelState, setPanelState] = useState<PanelVisibilityState>(
    PanelVisibilityState.None
  )

  const closeContentPanel = useCallback(() => {
    setPanelState(PanelVisibilityState.None)
  }, [setPanelState])

  const startAdd = useCallback(
    (event: ReactMouseEvent<HTMLAnchorElement, MouseEvent>) => {
      event.preventDefault()
      setPanelState(PanelVisibilityState.Add)
    },
    [setPanelState]
  )

  const startEdit = curry(
    (uuid: string, event: ReactMouseEvent<HTMLLIElement, MouseEvent>) => {
      event.preventDefault()
      setEditItemUUID(uuid)
      setPanelState(PanelVisibilityState.Edit)
    }
  )

  if (contentListingPending) {
    return <div className="site-page container">Loading...</div>
  }

  if (!listing) {
    return null
  }

  const configItem = website?.starter?.config?.collections.find(
    (config: TopLevelConfigItem) => config.name === contenttype
  )
  if (!configItem) {
    return null
  }

  return (
    <>
      <SiteContentEditor
        site={website}
        configItem={configItem}
        contentType={match.params.contenttype}
        uuid={editItemUUID}
        visibility={panelState === PanelVisibilityState.Edit}
        toggleVisibility={closeContentPanel}
        formType={ContentFormType.Edit}
        websiteContentListingRequest={runWebsiteContentListingRequest}
      />
      <SiteContentEditor
        site={website}
        // @ts-ignore
        configItem={configItem}
        contentType={match.params.contenttype}
        uuid={null}
        visibility={panelState === PanelVisibilityState.Add}
        toggleVisibility={closeContentPanel}
        formType={ContentFormType.Add}
        websiteContentListingRequest={runWebsiteContentListingRequest}
      />
      {isRepeatableCollectionItem(configItem) ? (
        <RepeatableContentListing
          configItem={configItem}
          listing={listing}
          startAdd={startAdd}
          startEdit={startEdit}
        />
      ) : (
        <SingletonContentListing
          configItem={configItem}
          listing={listing}
          startAdd={startAdd}
          startEdit={startEdit}
        />
      )}
      <PaginationControls
        listing={listing}
        previous={siteContentListingUrl
          .param({
            name,
            contentType: contenttype
          })
          .query({ offset: offset - WEBSITE_CONTENT_PAGE_SIZE })
          .toString()}
        next={siteContentListingUrl
          .param({
            name,
            contentType: contenttype
          })
          .query({ offset: offset + WEBSITE_CONTENT_PAGE_SIZE })
          .toString()}
      />
    </>
  )
}
