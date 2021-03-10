import React, { MouseEvent as ReactMouseEvent, useState } from "react"
import { useRouteMatch, NavLink } from "react-router-dom"
import { useRequest } from "redux-query-react"
import { useSelector } from "react-redux"

import SiteEditContent from "./SiteEditContent"

import { siteAddContentUrl, siteContentListingUrl } from "../lib/urls"
import { websiteContentListingRequest } from "../query-configs/websites"
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
  const { contenttype, name } = match.params
  const website = useSelector(getWebsiteDetailCursor)(name)
  const [{ isPending: contentListingPending }] = useRequest(
    websiteContentListingRequest(name, contenttype)
  )
  const listing = useSelector(getWebsiteContentListingCursor)(name, contenttype)
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
            <NavLink to={siteContentListingUrl(name, contenttype)}>
              {configItem.label} /
            </NavLink>
          </h3>
          <NavLink to={siteAddContentUrl(name, contenttype)}>
            Add {configItem.label}
          </NavLink>
        </div>
        <ul>
          {listing.map((item: WebsiteContentListItem) => (
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
      </div>
    </>
  )
}
