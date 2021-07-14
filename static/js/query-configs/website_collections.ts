import { QueryConfig } from "redux-query"
import { findIndex, mergeRight } from "ramda"

import { PaginatedResponse } from "./utils"

import {
  collectionsApiDetailUrl,
  collectionsApiUrl,
  wcItemsApiDetailUrl,
  wcItemsApiUrl
} from "../lib/urls"
import {
  WebsiteCollection,
  WebsiteCollectionItem
} from "../types/website_collections"
import { getCookie } from "../lib/api/util"
import {
  WCItemCreateFormFields,
  WCItemMoveFormFields,
  WebsiteCollectionFormFields
} from "../types/forms"
import { arrayMove } from "@dnd-kit/sortable"

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

export type WebsiteCollectionItemListing = Record<
  number,
  WebsiteCollectionItem[]
>

export const websiteCollectionItemsRequest = (id: number): QueryConfig => {
  return {
    url:       wcItemsApiUrl.param({ collectionId: id }).toString(),
    transform: (body: WebsiteCollectionItem[]) => ({
      websiteCollectionItems: {
        [id]: body
      }
    }),
    update: {
      websiteCollectionItems: mergeRight
    }
  }
}

export const createWebsiteCollectionItemMutation = (
  item: WCItemCreateFormFields,
  collectionId: number
): QueryConfig => ({
  url:       wcItemsApiUrl.param({ collectionId }).toString(),
  body:      item,
  transform: (body: WebsiteCollectionItem) => ({
    websiteCollectionItems: {
      [collectionId]: [body]
    }
  }),
  update: {
    websiteCollectionItems: (
      prev: WebsiteCollectionItemListing,
      next: WebsiteCollectionItemListing
    ) => {
      const previous = (prev ?? {})[collectionId] ?? []

      return {
        [collectionId]: [...previous, ...next[collectionId]]
      }
    }
  },
  options: {
    method:  "POST",
    headers: {
      "X-CSRFTOKEN": getCookie("csrftoken") || ""
    }
  }
})

/**
 * This mutation is for changing the position of
 * WebsiteCollectionItems.
 */
export const editWebsiteCollectionItemMutation = (
  item: WCItemMoveFormFields,
  collectionId: number,
  itemId: number
): QueryConfig => ({
  url: wcItemsApiDetailUrl
    .param({
      collectionId,
      itemId
    })
    .toString(),
  body:      item,
  transform: (body: WebsiteCollectionItem) => ({
    websiteCollectionItems: body
  }),
  update: {
    websiteCollectionItems: (
      prev: WebsiteCollectionItemListing,
      next: WebsiteCollectionItem
    ) => {
      const oldIndex = findIndex(
        item => item.id === next.id,
        prev[collectionId]
      )

      const newArray = [...prev[collectionId]]
      newArray[oldIndex] = next

      return {
        [collectionId]: arrayMove(newArray, oldIndex, next.position)
      }
    }
  },
  options: {
    method:  "PATCH",
    headers: {
      "X-CSRFTOKEN": getCookie("csrftoken") || ""
    }
  }
})
