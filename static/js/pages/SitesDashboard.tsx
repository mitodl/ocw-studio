import React from "react"
import { useSelector } from "react-redux"
import { useRequest } from "redux-query-react"
import { Link, RouteComponentProps } from "react-router-dom"

import Card from "../components/Card"
import PaginationControls from "../components/PaginationControls"

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
    <div className="px-4 dashboard">
      <div className="content">
        <div className="d-flex flex-direction-row align-items-center justify-content-between pb-3">
          <h3>Sites</h3>
          <Link className="btn blue-button add-new" to={newSiteUrl.toString()}>
            Add New
          </Link>
        </div>
        <Card>
          <ul className="listing ruled-list">
            {listing.results.map((site: Website) => (
              <li className="py-3" key={site.name}>
                <Link
                  className="site-link"
                  to={siteDetailUrl.param({ name: site.name }).toString()}
                >
                  {site.title}
                </Link>
                <div className="site-description">{siteDescription(site)}</div>
              </li>
            ))}
          </ul>
        </Card>
        <PaginationControls
          listing={listing}
          previous={sitesBaseUrl
            .query({ offset: offset - WEBSITES_PAGE_SIZE })
            .toString()}
          next={sitesBaseUrl
            .query({ offset: offset + WEBSITES_PAGE_SIZE })
            .toString()}
        />
      </div>
    </div>
  )
}
