import { QueryConfig } from "redux-query"

import { PaginatedResponse } from "./utils"

import { collectionsApiUrl } from "../lib/urls"
import { WebsiteCollection } from "../types/website_collections"

export type WebsiteCollectionDetails = Record<number, WebsiteCollection>

export type WebsiteCollectionListing = Record<number, PaginatedResponse<number>>

export type WebsiteCollectionListingResponse = PaginatedResponse<
  WebsiteCollection
>

export const websiteCollectionListRequest = (offset = 0): QueryConfig => ({
  url:       collectionsApiUrl.query({ offset }).toString(),
  transform: (body: WebsiteCollectionListingResponse) => {
    const websiteCollectionDetails: WebsiteCollectionDetails = Object.fromEntries(
      body.results.map((collection: WebsiteCollection) => [
        collection.id,
        collection
      ])
    )

    const websiteCollectionListing: WebsiteCollectionListing = {
      [offset]: {
        ...body,
        results: body.results.map(
          (collection: WebsiteCollection) => collection.id
        )
      }
    }

    return {
      websiteCollectionDetails,
      websiteCollectionListing
    }
  },

  update: {
    websiteCollectionListing: (
      prev: WebsiteCollectionListing,
      next: WebsiteCollectionListing
    ) =>
      prev ?
        {
          ...prev,
          ...next
        } :
        next,
    websiteCollectionDetails: (
      prev: WebsiteCollectionDetails,
      next: WebsiteCollectionDetails
    ): WebsiteCollectionDetails => ({
      ...prev,
      ...next
    })
  }
})
