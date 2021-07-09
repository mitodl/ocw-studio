import { QueryConfig } from "redux-query"

import { PaginatedResponse } from "./utils"

import { collectionsApiDetailUrl, collectionsApiUrl } from "../lib/urls"
import { WebsiteCollection } from "../types/website_collections"
import { getCookie } from "../lib/api/util"
import { WebsiteCollectionFormFields } from "../types/forms"

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

export const websiteCollectionRequest = (id: number): QueryConfig => ({
  url: collectionsApiDetailUrl
    .param({
      collectionId: id
    })
    .toString(),
  transform: (body: WebsiteCollection) => {
    return {
      websiteCollectionDetails: {
        [body.id]: body
      }
    }
  },
  update: {
    websiteCollectionDetails: (
      prev: WebsiteCollectionDetails,
      next: WebsiteCollectionDetails
    ): WebsiteCollectionDetails => ({
      ...prev,
      ...next
    })
  }
})

export const editWebsiteCollectionMutation = (
  collection: WebsiteCollection
): QueryConfig => ({
  url: collectionsApiDetailUrl
    .param({
      collectionId: collection.id
    })
    .toString(),
  body:    collection,
  options: {
    method:  "PATCH",
    headers: {
      "X-CSRFTOKEN": getCookie("csrftoken") || ""
    }
  },
  transform: response => ({
    websiteCollectionDetails: {
      [collection.id]: response
    }
  }),
  update: {
    websiteCollectionDetails: (prev, next) => ({
      ...prev,
      ...next
    })
  }
})

export const createWebsiteCollectionMutation = (
  collection: WebsiteCollectionFormFields
): QueryConfig => ({
  url:     collectionsApiUrl.toString(),
  body:    collection,
  options: {
    method:  "POST",
    headers: {
      "X-CSRFTOKEN": getCookie("csrftoken") || ""
    }
  },
  transform: response => ({
    websiteCollectionDetails: {
      [response.id]: response
    }
  }),
  update: {
    websiteCollectionDetails: (prev, next) => ({
      ...prev,
      ...next
    })
  }
})
