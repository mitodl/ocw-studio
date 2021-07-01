import { createSelector } from "reselect"
import { memoize } from "lodash"

import { ReduxState } from "../reducers"
import {
  WebsiteCollectionDetails,
  WebsiteCollectionListing,
  WebsiteCollectionListingResponse
} from "../query-configs/website_collections"

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
