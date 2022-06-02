import React from "react"
import { useSelector } from "react-redux"
import { useRequest } from "redux-query-react"
import { Link } from "react-router-dom"

import PaginationControls from "../components/PaginationControls"

import {
  WebsiteListingParams,
  websiteListingRequest,
  WebsiteListingResponse
} from "../query-configs/websites"
import { getWebsiteListingCursor } from "../selectors/websites"
import { newSiteUrl, siteDetailUrl } from "../lib/urls"
import { Website } from "../types/websites"
import DocumentTitle, { formatTitle } from "../components/DocumentTitle"
import { StudioList, StudioListItem } from "../components/StudioList"
import { useURLParamFilter, usePagination } from "../hooks/search"
import { usePermission } from "../hooks/permissions"
import { Permissions } from "../constants"

function getListingParams(search: string): WebsiteListingParams {
  const qsParams = new URLSearchParams(search)
  const offset = Number(qsParams.get("offset") ?? 0)
  const searchString = qsParams.get("q")

  return searchString ? { offset, search: searchString } : { offset }
}

export default function SitesDashboard(): JSX.Element {
  const { listingParams, searchInput, setSearchInput } = useURLParamFilter(
    getListingParams
  )

  useRequest(websiteListingRequest(listingParams))

  const listing: WebsiteListingResponse = useSelector(getWebsiteListingCursor)(
    listingParams.offset
  )
  const pages = usePagination(listing.count ?? 0)

  const canAddSites = usePermission(Permissions.canCreateSites)

  return (
    <div className="px-4 dashboard">
      <DocumentTitle title={formatTitle("Sites")} />
      <div className="content">
        <div className="d-flex flex-direction-row align-items-center justify-content-between pb-3">
          <div>
            <h2 className="my-2 p-0">Sites</h2>
          </div>
          <div className="d-flex align-items-center">
            <input
              placeholder="Search for a site"
              className="site-search-input mr-5 form-control"
              value={searchInput}
              onChange={setSearchInput}
            />
            {canAddSites ? (
              <Link
                className="btn cyan-button larger add-new"
                to={newSiteUrl.toString()}
              >
                Add Site
              </Link>
            ) : null}
          </div>
        </div>
        <StudioList>
          {listing.results.map((site: Website) => (
            <StudioListItem
              title={site.title}
              subtitle={site.short_id}
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
        <PaginationControls previous={pages.previous} next={pages.next} />
      </div>
    </div>
  )
}
