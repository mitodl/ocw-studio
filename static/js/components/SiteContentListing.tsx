import React, { MouseEvent as ReactMouseEvent, useState } from "react"
import { useRouteMatch, NavLink, useLocation } from "react-router-dom"
import { useRequest } from "redux-query-react"
import { useSelector } from "react-redux"

import SiteEditContent from "./SiteEditContent"
import PaginationControls from "./PaginationControls"
import Card from "./Card"

import { WEBSITE_CONTENT_PAGE_SIZE } from "../constants"
import { siteAddContentUrl, siteContentListingUrl } from "../lib/urls"
import {
  websiteContentListingRequest,
  WebsiteContentListingResponse
} from "../query-configs/websites"
import {
  getWebsiteDetailCursor,
  getWebsiteContentListingCursor
} from "../selectors/websites"

import { ConfigItem, WebsiteContentListItem } from "../types/websites"

interface MatchParams {
  contenttype: string
  name: string
}
export default function SiteContentListing(): JSX.Element | null {
  const match = useRouteMatch<MatchParams>()
  const { search } = useLocation()
  const offset = Number(new URLSearchParams(search).get("offset") ?? 0)
  const { contenttype, name } = match.params

  const website = useSelector(getWebsiteDetailCursor)(name)
  const [{ isPending: contentListingPending }] = useRequest(
    websiteContentListingRequest(name, contenttype, offset)
  )
  const listing: WebsiteContentListingResponse = useSelector(
    getWebsiteContentListingCursor
  )(name, contenttype, offset)
  const [editUuid, setEditUuid] = useState<string | null>(null)
  const [editVisibility, setEditVisibility] = useState<boolean>(false)

  if (contentListingPending) {
    return <div className="site-page container">Loading...</div>
  }

  if (!listing) {
    return null
  }

  const configItem = website?.starter?.config?.collections.find(
    (config: ConfigItem) => config.name === contenttype
  )
  if (!configItem) {
    return null
  }

  const startEdit = (uuid: string) => (
    event: ReactMouseEvent<HTMLAnchorElement, MouseEvent>
  ) => {
    event.preventDefault()
    setEditUuid(uuid)
    setEditVisibility(true)
  }

  const toggleEditVisibility = () => setEditVisibility(!editVisibility)

  return (
    <>
      {editUuid ? (
        <SiteEditContent
          site={website}
          configItem={configItem}
          uuid={editUuid}
          visibility={editVisibility}
          toggleVisibility={toggleEditVisibility}
        />
      ) : null}
      <div>
        <Card>
          <div className="d-flex flex-direction-row align-items-center justify-content-between pb-3">
            <h3>
              <NavLink
                to={siteContentListingUrl
                  .param({ name, contentType: contenttype })
                  .toString()}
              >
                {configItem.label}
              </NavLink>
            </h3>
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
              <li key={item.uuid} className="py-3">
                <div className="d-flex flex-direction-row align-items-center justify-content-between">
                  <span>{item.title}</span>
                  <a className="edit" onClick={startEdit(item.uuid)}>
                    Edit
                  </a>
                </div>
              </li>
            ))}
          </ul>
        </Card>
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
      </div>
    </>
  )
}
