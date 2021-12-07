import React from "react"
import { useSelector } from "react-redux"
import { useRequest } from "redux-query-react"
import { Link, useHistory, useLocation } from "react-router-dom"

import PaginationControls from "../components/PaginationControls"

import {
  WebsiteListingParams,
  websiteListingRequest,
  WebsiteListingResponse
} from "../query-configs/websites"
import { getWebsiteListingCursor } from "../selectors/websites"
import { newSiteUrl, siteDetailUrl, sitesBaseUrl } from "../lib/urls"
import { WEBSITES_PAGE_SIZE } from "../constants"
import { Website } from "../types/websites"
import DocumentTitle, { formatTitle } from "../components/DocumentTitle"
import { StudioList, StudioListItem } from "../components/StudioList"
import { useTextInputState } from "../hooks/state"
import { useDebouncedEffect } from "../hooks/effect"

export function siteDescription(site: Website): string | null {
  const courseNumber = (site.metadata?.course_numbers ?? [])[0]
  const term = site.metadata?.term

  if (courseNumber && term) {
    return `${courseNumber} - ${term}`
  }
  return null
}

export default function SitesDashboard(): JSX.Element {
  const { search, pathname } = useLocation()
  const history = useHistory()
  const qsParams = new URLSearchParams(search)

  const offset = Number(qsParams.get("offset") ?? 0)
  const searchString = qsParams.get("q")

  const listingParams: WebsiteListingParams = searchString ?
    {
      offset,
      search: searchString
    } :
    {
      offset
    }

  const [{ isPending }] = useRequest(websiteListingRequest(listingParams))

  const listing: WebsiteListingResponse = useSelector(getWebsiteListingCursor)(
    offset
  )

  const [searchInput, setSearchInput] = useTextInputState()

  useDebouncedEffect(
    () => {
      const currentSeach = searchString ?? ""
      if (searchInput !== currentSeach) {
        const newParams = new URLSearchParams()
        newParams.set("offset", String(offset))
        newParams.set("q", searchInput)
        history.replace({
          pathname,
          search: newParams.toString()
        })
      }
    },
    [searchInput, pathname, searchString, offset],
    600
  )

  if (isPending || !listing) {
    return <div className="site-page container">Loading...</div>
  }

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
            <Link
              className="btn cyan-button larger add-new"
              to={newSiteUrl.toString()}
            >
              Add Site
            </Link>
          </div>
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
            .query({ ...listingParams, offset: offset - WEBSITES_PAGE_SIZE })
            .toString()}
          next={sitesBaseUrl
            .query({ ...listingParams, offset: offset + WEBSITES_PAGE_SIZE })
            .toString()}
        />
      </div>
    </div>
  )
}
