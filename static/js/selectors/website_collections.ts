import { createSelector } from "reselect"
import { memoize } from "lodash"

import { ReduxState } from "../reducers"
import {
  WebsiteCollectionDetails,
  WebsiteCollectionItemListing,
  WebsiteCollectionListing,
  WebsiteCollectionListingResponse
} from "../query-configs/website_collections"
import { WebsiteCollectionItem } from "../types/website_collections"

export const getWebsiteCollectionDetailCursor = createSelector(
  (state: ReduxState) => state.entities?.websiteCollectionDetails ?? {},
  (collections: WebsiteCollectionDetails) =>
    memoize((id: number) => collections[id])
)

export const getWebsiteCollectionListingCursor = createSelector(
  (state: ReduxState) => state.entities?.websiteCollectionListing ?? {},
  getWebsiteCollectionDetailCursor,
  (listing: WebsiteCollectionListing, websiteContentDetailCursor) =>
    memoize(
      (offset: number): WebsiteCollectionListingResponse => {
        const response = listing[offset] ?? {}

        return {
          ...response,
          results: (response?.results ?? []).map(websiteContentDetailCursor)
        }
      }
    )
)

/**
 * Selector to get a cursor for WebsiteCollectionItems.
 *
 * This cursor takes a WebsiteCollection id and returns an array
 * of WebsiteCollectionItems.
 */
export const getWebsiteCollectionItemsCursor = createSelector(
  (state: ReduxState) => state.entities?.websiteCollectionItems ?? {},
  (listing: WebsiteCollectionItemListing) =>
    memoize((id: number): WebsiteCollectionItem[] => listing[id] ?? [])
)
