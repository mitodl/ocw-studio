import { ActionPromiseValue, QueryConfig } from "redux-query"
import { merge, reject, propEq, compose, evolve, when, assoc, map } from "ramda"

import { nextState } from "./utils"
import { getCookie } from "../lib/api/util"
import { DEFAULT_POST_OPTIONS } from "../lib/redux_query"
import {
  siteApi,
  startersApi,
  siteApiCollaboratorsDetailUrl,
  siteApiCollaboratorsUrl,
  siteApiListingUrl,
  siteApiDetailUrl,
  siteApiContentListingUrl,
  siteApiContentDetailUrl,
  siteApiContentUrl
} from "../lib/urls"

import {
  ContentListingParams,
  NewWebsitePayload,
  Website,
  WebsiteCollaborator,
  WebsiteCollaboratorFormData,
  WebsiteContent,
  WebsiteContentListItem,
  WebsiteStarter
} from "../types/websites"

interface PaginatedResponse<Item> {
  count: number | null
  next: string | null
  previous: string | null
  results: Item[]
}
type WebsiteDetails = Record<string, Website>

export const getTransformedWebsiteName = (
  response: ActionPromiseValue<Record<string, WebsiteDetails>>
): string | null => {
  const transformedWebsiteKeys = Object.keys(
    response.transformed?.websiteDetails || {}
  )
  if (transformedWebsiteKeys.length === 0) {
    return null
  }
  return transformedWebsiteKeys[0]
}

export type WebsiteListingResponse = PaginatedResponse<Website>

type WebsitesListing = Record<string, string[]> // offset to list of site names

export const websiteListingRequest = (offset: number): QueryConfig => ({
  url:       siteApiListingUrl.query({ offset }).toString(),
  transform: (body: WebsiteListingResponse) => {
    const details = {}
    for (const site of body.results) {
      details[site.name] = site
    }

    return {
      websitesListing: {
        [`${offset}`]: {
          ...body,
          results: body.results.map(result => result.name)
        }
      },
      websiteDetails: details
    }
  },
  update: {
    websitesListing: (prev: WebsitesListing, next: WebsitesListing) => ({
      ...prev,
      ...next
    }),
    websiteDetails: (prev: WebsiteDetails, next: WebsiteDetails) => ({
      ...prev,
      ...next
    })
  },
  force: true // try to prevent stale information
})

export const websiteDetailRequest = (name: string): QueryConfig => ({
  url:       siteApiDetailUrl.param({ name }).toString(),
  transform: (body: Website) => ({
    websiteDetails: {
      [name]: body
    }
  }),
  update: {
    websiteDetails: (prev: WebsiteDetails, next: WebsiteDetails) => ({
      ...prev,
      ...next
    })
  },
  force: true // force a refresh to update incomplete information from listing API
})

export const websiteMutation = (payload: NewWebsitePayload): QueryConfig => ({
  url:     siteApi.toString(),
  options: {
    method:  "POST",
    headers: {
      "X-CSRFTOKEN": getCookie("csrftoken") || ""
    }
  },
  body:      payload,
  transform: (body: Website) => ({
    websiteDetails: {
      [body.name]: body
    }
  }),
  update: {
    websiteDetails: (prev: WebsiteDetails, next: WebsiteDetails) => ({
      ...prev,
      ...next
    })
  }
})

export const websiteStartersRequest = (): QueryConfig => ({
  url:       startersApi.toString(),
  transform: (results: Array<WebsiteStarter>) => ({
    starters: results
  }),
  update: {
    starters: nextState
  }
})

export const websiteCollaboratorsRequest = (name: string): QueryConfig => ({
  url:       siteApiCollaboratorsUrl.param({ name }).toString(),
  transform: (body: { results: WebsiteCollaborator[] }) => ({
    collaborators: {
      [name]: body.results || []
    }
  }),
  update: {
    collaborators: merge
  }
})

export const deleteWebsiteCollaboratorMutation = (
  websiteName: string,
  collaborator: WebsiteCollaborator
): QueryConfig => {
  const evictCollaborator = reject(propEq("user_id", collaborator.user_id))
  return {
    queryKey: "deleteWebsiteCollaboratorMutation",
    url:      siteApiCollaboratorsDetailUrl
      .param({
        name:   websiteName,
        userId: collaborator.user_id
      })
      .toString(),
    optimisticUpdate: {
      // evict the item
      collaborators: evolve({
        [websiteName]: compose(
          // @ts-ignore
          evictCollaborator,
          (value: WebsiteCollaborator) => value || []
        )
      })
    },
    // @ts-ignore
    options: {
      method: "DELETE",
      ...DEFAULT_POST_OPTIONS
    }
  }
}

export const editWebsiteCollaboratorMutation = (
  websiteName: string,
  collaborator: WebsiteCollaborator,
  role: string
): QueryConfig => {
  const alterRole = map(
    when(propEq("user_id", collaborator.user_id), assoc("role", role))
  )
  return {
    queryKey: "editWebsiteCollaboratorMutation",
    body:     { role },
    url:      siteApiCollaboratorsDetailUrl
      .param({
        name:   websiteName,
        userId: collaborator.user_id
      })
      .toString(),
    optimisticUpdate: {
      collaborators: evolve({
        [websiteName]: compose(
          alterRole,
          (value: WebsiteCollaborator[]) => value || []
        )
      })
    },
    // @ts-ignore
    options: {
      method: "PATCH",
      ...DEFAULT_POST_OPTIONS
    }
  }
}

export const createWebsiteCollaboratorMutation = (
  websiteName: string,
  item: WebsiteCollaboratorFormData
): QueryConfig => {
  return {
    queryKey:  "editWebsiteCollaboratorMutation",
    body:      { ...item },
    url:       siteApiCollaboratorsUrl.param({ name: websiteName }).toString(),
    transform: (body: WebsiteCollaborator) => ({
      collaborators: {
        [websiteName]: [body]
      }
    }),
    update: {
      collaborators: (
        prev: Record<string, WebsiteCollaborator[]>,
        next: Record<string, WebsiteCollaborator[]>
      ) => {
        next[websiteName] = next[websiteName].concat(prev[websiteName])
        return { ...prev, ...next }
      }
    },
    // @ts-ignore
    options: {
      method: "POST",
      ...DEFAULT_POST_OPTIONS
    }
  }
}

export type WebsiteContentListingResponse = PaginatedResponse<
  WebsiteContentListItem
>
type WebsiteContentListing = Record<string, string[]> // website name mapped to list of text IDs
export const contentListingKey = (
  listingParams: ContentListingParams
): string =>
  JSON.stringify([listingParams.name, listingParams.type, listingParams.offset])

export const websiteContentListingRequest = (
  listingParams: ContentListingParams
): QueryConfig => {
  const { name, type, offset } = listingParams
  const url = siteApiContentListingUrl.param({ name }).query({ type, offset })
  return {
    url:       url.toString(),
    transform: (body: WebsiteContentListingResponse) => {
      const details = {}
      for (const item of body.results) {
        details[item.text_id] = item
      }
      return {
        websiteContentListing: {
          [contentListingKey(listingParams)]: {
            ...body,
            results: body.results.map(item => item.text_id)
          }
        },
        websiteContentDetails: details
      }
    },
    update: {
      websiteContentListing: (
        prev: WebsiteContentListing,
        next: WebsiteContentListing
      ) => ({
        ...prev,
        ...next
      }),
      websiteContentDetails: (
        prev: WebsiteContentDetails,
        next: WebsiteContentDetails
      ) => ({
        ...prev,
        ...next
      })
    },
    force: true // try to prevent stale information
  }
}

type WebsiteContentDetails = Record<string, WebsiteContent>
export const websiteContentDetailRequest = (
  name: string,
  textId: string
): QueryConfig => ({
  url:       siteApiContentDetailUrl.param({ name, textId }).toString(),
  transform: (body: WebsiteContent) => ({
    websiteContentDetails: {
      [textId]: body
    }
  }),
  update: {
    websiteContentListing: (
      prev: WebsiteContentListing,
      next: WebsiteContentListing
    ) => ({
      ...prev,
      ...next
    }),
    websiteContentDetails: (
      prev: WebsiteContentDetails,
      next: WebsiteContentDetails
    ) => ({
      ...prev,
      ...next
    })
  },
  force: true // some data may be fetched in the collection view which is incomplete
})

export type EditWebsiteContentPayload = {
  title?: string
  content?: string
  body?: string
  metadata?: any
  file?: File
}
export const editWebsiteContentMutation = (
  site: Website,
  textId: string,
  contentType: string,
  payload: EditWebsiteContentPayload | FormData
): QueryConfig => ({
  url: siteApiContentDetailUrl
    .param({ name: site.name, textId: textId })
    .toString(),
  options: {
    method:  "PATCH",
    headers: {
      "X-CSRFTOKEN": getCookie("csrftoken") || ""
    }
  },
  body:      payload,
  transform: (response: WebsiteContent) => ({
    websiteContentDetails: {
      [textId]: response
    }
  }),
  update: {
    websiteContentDetails: (
      prev: WebsiteContentDetails,
      next: WebsiteContentDetails
    ) => ({
      ...prev,
      ...next
    })
  }
})

export type NewWebsiteContentPayload = {
  title: string
  type: string
  content?: string
  body?: string
  metadata: any
  // eslint-disable-next-line camelcase
  text_id?: string
}
export const createWebsiteContentMutation = (
  siteName: string,
  payload: NewWebsiteContentPayload
): QueryConfig => ({
  url:     siteApiContentUrl.param({ name: siteName }).toString(),
  options: {
    method:  "POST",
    headers: {
      "X-CSRFTOKEN": getCookie("csrftoken") || ""
    }
  },
  body:      payload,
  transform: (response: WebsiteContent) => ({
    websiteContentDetails: {
      [response.text_id]: response
    }
  }),
  update: {
    websiteContentDetails: (
      prev: WebsiteContentDetails,
      next: WebsiteContentDetails
    ) => ({
      ...prev,
      ...next
    })
  }
})
