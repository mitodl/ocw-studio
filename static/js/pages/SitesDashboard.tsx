import React, { useEffect, useState } from "react"
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

function getListingParams(search: string): WebsiteListingParams {
  const qsParams = new URLSearchParams(search)
  const offset = Number(qsParams.get("offset") ?? 0)
  const searchString = qsParams.get("q")

  return searchString ? { offset, search: searchString } : { offset }
}

export default function SitesDashboard(): JSX.Element {
  const { search } = useLocation()
  const history = useHistory()

  const [listingParams, setListingParams] = useState<WebsiteListingParams>(() =>
    getListingParams(search)
  )

  const [searchInput, setSearchInput] = useTextInputState(
    listingParams.search ?? ""
  )

  /**
   * This debounced effect listens on the search input and, when it is
   * different from the value current set on `listingParams`, will format a new
   * query string (with offset reset to zero) and push that onto the history
   * stack.
   *
   * We are using the URL and the browser's history mechanism as our source of
   * truth for when we are going to re-run the search and whatnot. So in this
   * call we're just concerned with debouncing user input (on the text input)
   * and then basically echoing it up to the URL bar every so often. Below we
   * listen to the `search` param and regenerate `listingParams` when it
   * changes.
   */
  useDebouncedEffect(
    () => {
      const currentSearch = listingParams.search ?? ""
      if (searchInput !== currentSearch) {
        const newParams = new URLSearchParams()
        if (searchInput) {
          newParams.set("q", searchInput)
        }
        const newSearch = newParams.toString()
        history.push(`?${newSearch}`)
      }
    },
    [searchInput, listingParams],
    600
  )

  /**
   * Whenever the search params in the URL change we want to generate a new
   * value for `listingParams`. This will in turn trigger the request to re-run
   * and fetch new results.
   */
  useEffect(() => {
    setListingParams(getListingParams(search))
  }, [search, setListingParams])

  useRequest(websiteListingRequest(listingParams))

  const listing: WebsiteListingResponse = useSelector(getWebsiteListingCursor)(
    listingParams.offset
  )

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
            .query({
              ...(listingParams.search ? { q: listingParams.search } : {}),
              offset: listingParams.offset - WEBSITES_PAGE_SIZE
            })
            .toString()}
          next={sitesBaseUrl
            .query({
              ...(listingParams.search ? { q: listingParams.search } : {}),
              offset: listingParams.offset + WEBSITES_PAGE_SIZE
            })
            .toString()}
        />
      </div>
    </div>
  )
}
