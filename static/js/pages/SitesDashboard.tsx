import React from "react"
import { useSelector } from "react-redux"
import { useRequest } from "redux-query-react"
import { Link, RouteComponentProps } from "react-router-dom"

import PaginationControls from "../components/PaginationControls"

import {
  websiteListingRequest,
  WebsiteListingResponse
} from "../query-configs/websites"
import { getWebsiteListingCursor } from "../selectors/websites"
import { newSiteUrl, siteDetailUrl, sitesBaseUrl } from "../lib/urls"
import { WEBSITES_PAGE_SIZE } from "../constants"
import { Website } from "../types/websites"
import DocumentTitle, { formatTitle } from "../components/DocumentTitle"
import { StudioList, StudioListItem } from "../components/StudioList"

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
      <DocumentTitle title={formatTitle("Sites")} />
      <div className="content">
        <div className="d-flex flex-direction-row align-items-center justify-content-between pb-3">
          <h2 className="my-2 p-0">Sites</h2>
          <Link
            className="btn cyan-button larger add-new"
            to={newSiteUrl.toString()}
          >
            Add Site
          </Link>
        </div>
        <StudioList>
          {listing.results.map((site: Website) => (
            <StudioListItem
              title={site.title}
              subtitle={siteDescription(site) ?? ""}
              to={siteDetailUrl.param({ name: site.name }).toString()}
              key={site.uuid}
            >
              {site.publish_date ? (
                <div className="text-success">Published</div>
              ) : (
                <div className="text-dark">Draft</div>
              )}
            </StudioListItem>
          ))}
        </StudioList>
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
