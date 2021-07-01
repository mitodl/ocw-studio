import React from "react"
import { useRequest } from "redux-query-react"
import { useSelector } from "react-redux"
import { useLocation } from "react-router-dom"

import PaginationControls from "../components/PaginationControls"
import Card from "../components/Card"

import { WEBSITE_CONTENT_PAGE_SIZE } from "../constants"
import {
  websiteCollectionListRequest,
  WebsiteCollectionListingResponse
} from "../query-configs/website_collections"
import { getWebsiteCollectionListingCursor } from "../selectors/website_collections"
import { WebsiteCollection } from "../types/website_collections"
import { collectionsBaseUrl } from "../lib/urls"

export default function WebsiteCollectionsPage(): JSX.Element {
  const { search } = useLocation()

  const offset = Number(new URLSearchParams(search).get("offset") ?? 0)

  useRequest(websiteCollectionListRequest(offset))

  const websiteCollectionsListingCursor = useSelector(
    getWebsiteCollectionListingCursor
  )

  const listing: WebsiteCollectionListingResponse = websiteCollectionsListingCursor(
    offset
  )

  return (
    <div className="px-4 dashboard">
      <div className="content">
        <div className="d-flex flex-direction-row align-items-center justify-content-between pb-3">
          <h3>Collections</h3>
        </div>
        <Card>
          <ul className="ruled-list">
            {listing.results.map((collection: WebsiteCollection) => (
              <li className="py-3" key={collection.id}>
                <a>{collection.title}</a>
                <div className="text-gray">{collection.description}</div>
              </li>
            ))}
          </ul>
          <PaginationControls
            listing={listing}
            previous={collectionsBaseUrl
              .query({ offset: offset - WEBSITE_CONTENT_PAGE_SIZE })
              .toString()}
            next={collectionsBaseUrl
              .query({ offset: offset + WEBSITE_CONTENT_PAGE_SIZE })
              .toString()}
          />
        </Card>
      </div>
    </div>
  )
}
