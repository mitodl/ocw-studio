import React, { MouseEvent as ReactMouseEvent, useState } from "react"
import { useRouteMatch, NavLink, useLocation } from "react-router-dom"
import { useRequest } from "redux-query-react"
import { useSelector } from "react-redux"
import { curry } from "ramda"

import SiteEditContent from "./SiteEditContent"
import PaginationControls from "./PaginationControls"
import Card from "./Card"

import { WEBSITE_CONTENT_PAGE_SIZE } from "../constants"
import { siteAddContentUrl, siteContentListingUrl } from "../lib/urls"
import { isRepeatableCollectionItem } from "../lib/site_content"
import {
  websiteContentListingRequest,
  WebsiteContentListingResponse
} from "../query-configs/websites"
import {
  getWebsiteDetailCursor,
  getWebsiteContentListingCursor
} from "../selectors/websites"

import {
  RepeatableConfigItem,
  SingletonsConfigItem,
  TopLevelConfigItem,
  EditableConfigItem,
  WebsiteContentListItem,
  ContentListingParams
} from "../types/websites"

interface MatchParams {
  contenttype: string
  name: string
}

interface ListingComponentParams {
  listing: WebsiteContentListingResponse
  contenttype: string
  name: string
  startEdit: (
    uuid: string,
    configItem: EditableConfigItem
  ) => (event: ReactMouseEvent<HTMLLIElement, MouseEvent>) => void
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
  const { configItem, listing, contenttype, name, startEdit } = props

  return (
    <div>
      <Card>
        <div className="d-flex flex-direction-row align-items-center justify-content-between pb-3">
          <h3>{configItem.label}</h3>
          <NavLink
            className="btn blue-button"
            to={siteAddContentUrl
              .param({ name, contentType: contenttype })
              .toString()}
          >
            Add {configItem.label}
          </NavLink>
        </div>
        <ul className="ruled-list">
          {listing.results.map((item: WebsiteContentListItem) => (
            <li
              key={item.uuid}
              className="py-3 listing-result"
              onClick={startEdit(item.uuid, configItem)}
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
  const [{ isPending: contentListingPending }] = useRequest(
    websiteContentListingRequest(listingParams)
  )
  const listing: WebsiteContentListingResponse = useSelector(
    getWebsiteContentListingCursor
  )(listingParams)
  const [editedItem, setEditedItem] = useState<{
    uuid: string
    configItem: EditableConfigItem
  } | null>(null)
  const [isEditPanelVisible, setEditPanelVisibility] = useState<boolean>(false)

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

  const startEdit = curry(
    (
      uuid: string,
      configItem: EditableConfigItem,
      event: ReactMouseEvent<HTMLLIElement, MouseEvent>
    ) => {
      event.preventDefault()
      setEditedItem({ uuid, configItem })
      setEditPanelVisibility(true)
    }
  )
  const toggleEditPanelVisibility = () =>
    setEditPanelVisibility(!isEditPanelVisible)

  const resultsBody = isRepeatableCollectionItem(configItem) ? (
    <RepeatableContentListing
      configItem={configItem}
      listing={listing}
      contenttype={contenttype}
      name={name}
      startEdit={startEdit}
    />
  ) : (
    <SingletonContentListing
      configItem={configItem}
      listing={listing}
      contenttype={contenttype}
      name={name}
      startEdit={startEdit}
    />
  )

  return (
    <>
      {editedItem ? (
        <SiteEditContent
          site={website}
          configItem={editedItem.configItem}
          uuid={editedItem.uuid}
          visibility={isEditPanelVisible}
          toggleVisibility={toggleEditPanelVisibility}
        />
      ) : null}
      {resultsBody}
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
