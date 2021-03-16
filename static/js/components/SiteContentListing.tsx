import React, { MouseEvent as ReactMouseEvent, useState } from "react"
import {
  useRouteMatch,
  NavLink,
  RouteComponentProps,
  Link
} from "react-router-dom"
import { useRequest } from "redux-query-react"
import { useSelector } from "react-redux"

import SiteEditContent from "./SiteEditContent"

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
export default function SiteContentListing(
  props: RouteComponentProps<Record<string, never>>
): JSX.Element | null {
  const match = useRouteMatch<MatchParams>()
  const {
    location: { search }
  } = props
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
      <div className="px-4">
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
            to={siteAddContentUrl
              .param({ name, contentType: contenttype })
              .toString()}
          >
            Add {configItem.label}
          </NavLink>
        </div>
        <ul>
          {listing.results.map((item: WebsiteContentListItem) => (
            <li key={item.uuid}>
              <div className="d-flex flex-direction-row align-items-center justify-content-between">
                <span>{item.title}</span>
                <a className="edit" onClick={startEdit(item.uuid)}>
                  Edit
                </a>
              </div>
              <hr />
            </li>
          ))}
        </ul>
        <div className="pagination justify-content-center">
          {listing.previous ? (
            <Link
              to={siteContentListingUrl
                .param({
                  name,
                  contentType: contenttype
                })
                .query({ offset: offset - WEBSITE_CONTENT_PAGE_SIZE })
                .toString()}
              className="previous"
            >
              <i className="material-icons">keyboard_arrow_left</i>
            </Link>
          ) : null}
          &nbsp;
          {listing.next ? (
            <Link
              to={siteContentListingUrl
                .param({
                  name,
                  contentType: contenttype
                })
                .query({ offset: offset + WEBSITE_CONTENT_PAGE_SIZE })
                .toString()}
              className="next"
            >
              <i className="material-icons">keyboard_arrow_right</i>
            </Link>
          ) : null}
        </div>
      </div>
    </>
  )
}
