import React from "react"
import { useSelector } from "react-redux"
import { useRequest } from "redux-query-react"
import { Link, RouteComponentProps } from "react-router-dom"

import {
  websiteListingRequest,
  WebsiteListingResponse
} from "../query-configs/websites"
import { getWebsiteListingCursor } from "../selectors/websites"
import { newSiteUrl, siteDetailUrl, sitesBaseUrl } from "../lib/urls"
import { WEBSITES_PAGE_SIZE } from "../constants"
import { Website } from "../types/websites"

export function siteDescription(site: Website): string | null {
  const courseNumber = (site.metadata?.course_numbers ?? [])[0]
  const term = site.metadata?.term

  if (courseNumber && term) {
    return `${courseNumber} - ${term}`
  }
  return null
}

export default function SitesDashboard(
  props: RouteComponentProps<Record<string, never>>
): JSX.Element {
  const {
    location: { search }
  } = props
  const offset = Number(new URLSearchParams(search).get("offset") ?? 0)
  const [{ isPending }] = useRequest(websiteListingRequest(offset))
  const listing: WebsiteListingResponse = useSelector(getWebsiteListingCursor)(
    offset
  )

  if (isPending || !listing) {
    return <div className="site-page container">Loading...</div>
  }

  return (
    <div className="px-4 sites-dashboard">
      <div className="content">
        <div className="d-flex flex-direction-row align-items-center justify-content-between pb-3">
          <h3>Courses /</h3>
          <Link className="add-new" to={newSiteUrl.toString()}>
            Add New
          </Link>
        </div>
        <ul className="listing">
          {listing.results.map((site: Website) => (
            <li key={site.name}>
              <Link to={siteDetailUrl.param({ name: site.name }).toString()}>
                {site.title}
              </Link>
              <div className="site-description">{siteDescription(site)}</div>
              <hr />
            </li>
          ))}
        </ul>
        <div className="pagination justify-content-center">
          {listing.previous ? (
            <Link
              to={sitesBaseUrl
                .query({ offset: offset - WEBSITES_PAGE_SIZE })
                .toString()}
              className="previous"
            >
              <i className="material-icons">keyboard_arrow_left</i>
            </Link>
          ) : null}
          &nbsp;
          {listing.next ? (
            <Link
              to={sitesBaseUrl
                .query({ offset: offset + WEBSITES_PAGE_SIZE })
                .toString()}
              className="next"
            >
              <i className="material-icons">keyboard_arrow_right</i>
            </Link>
          ) : null}
        </div>
      </div>
    </div>
  )
}
