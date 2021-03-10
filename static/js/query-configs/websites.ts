import { ActionPromiseValue, QueryConfig } from "redux-query"
import { merge, reject, propEq, compose, evolve, when, assoc, map } from "ramda"

import { nextState } from "./utils"
import { getCookie } from "../lib/api/util"
import { DEFAULT_POST_OPTIONS } from "../lib/redux_query"
import {
  siteApiCollaboratorsDetailUrl,
  siteApiCollaboratorsUrl,
  siteApiUrl
} from "../lib/urls"

import {
  NewWebsitePayload,
  Website,
  WebsiteCollaborator,
  WebsiteCollaboratorFormData,
  WebsiteContent,
  WebsiteContentListItem,
  WebsiteStarter
} from "../types/websites"

interface WebsiteDetails {
  [key: string]: Website
}

export const getTransformedWebsiteName = (
  response: ActionPromiseValue<{ [key: string]: WebsiteDetails }>
): string | null => {
  const transformedWebsiteKeys = Object.keys(
    response.transformed?.websiteDetails || {}
  )
  if (transformedWebsiteKeys.length === 0) {
    return null
  }
  return transformedWebsiteKeys[0]
}

export const websiteDetailRequest = (name: string): QueryConfig => ({
  url:       siteApiUrl(name),
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
  }
})

export const websiteMutation = (payload: NewWebsitePayload): QueryConfig => ({
  url:     "/api/websites/",
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
  url:       `/api/starters/`,
  transform: (results: Array<WebsiteStarter>) => ({
    starters: results
  }),
  update: {
    starters: nextState
  }
})

export const websiteCollaboratorsRequest = (name: string): QueryConfig => ({
  url:       siteApiCollaboratorsUrl(name),
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
  const evictCollaborator = reject(propEq("username", collaborator.username))
  return {
    queryKey: "deleteWebsiteCollaboratorMutation",
    url:      siteApiCollaboratorsDetailUrl(
      websiteName,
      collaborator.username
    ).toString(),
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
    when(propEq("username", collaborator.username), assoc("role", role))
  )
  return {
    queryKey: "editWebsiteCollaboratorMutation",
    body:     { role },
    url:      siteApiCollaboratorsDetailUrl(
      websiteName,
      collaborator.username
    ).toString(),
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
    url:       siteApiCollaboratorsUrl(websiteName).toString(),
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

interface WebsiteContentListing {
  [key: string]: WebsiteContentListItem[]
}
interface WebsiteContentDetails {
  [uuid: string]: WebsiteContent
}

export const contentListingKey = (name: string, type: string): string =>
  `${name}_${type}`
export const websiteContentListingRequest = (
  name: string,
  type: string
): QueryConfig => ({
  url:       `/api/websites/${name}/content/?type=${type}`,
  transform: (body: WebsiteContentListItem[]) => ({
    websiteContentListing: {
      [contentListingKey(name, type)]: body
    }
  }),
  update: {
    websiteContentListing: (
      prev: WebsiteContentListing,
      next: WebsiteContentListing
    ) => ({
      ...prev,
      ...next
    })
  }
})

export const websiteContentDetailRequest = (
  name: string,
  uuid: string
): QueryConfig => ({
  url:       `/api/websites/${name}/content/${uuid}/`,
  transform: (body: WebsiteContent) => ({
    websiteContentDetails: {
      [uuid]: body
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

export type EditWebsiteContentPayload = {
  title?: string
  content?: string
  body?: string
  metadata?: {
    [key: string]: string
  }
}
export const editWebsiteContentMutation = (
  site: Website,
  uuid: string,
  contentType: string,
  payload: EditWebsiteContentPayload
): QueryConfig => ({
  url:     `/api/websites/${site.name}/content/${uuid}/`,
  options: {
    method:  "PATCH",
    headers: {
      "X-CSRFTOKEN": getCookie("csrftoken") || ""
    }
  },
  body:      payload,
  transform: (response: WebsiteContent) => ({
    websiteContentDetails: {
      [uuid]: response
    },
    websiteContentListing: response
  }),
  update: {
    websiteContentDetails: (
      prev: WebsiteContentDetails,
      next: WebsiteContentDetails
    ) => ({
      ...prev,
      ...next
    }),
    websiteContentListing: (
      prev: WebsiteContentListing,
      next: WebsiteContent
    ) => {
      const key = contentListingKey(site.name, contentType)
      const oldList: WebsiteContentListItem[] = prev[key] ?? []
      return {
        ...prev,
        // we'll need to sort this once we figure out a preferred order for the content listing
        [key]: oldList.map(item => (item.uuid === next.uuid ? next : item))
      }
    }
  }
})

export type NewWebsiteContentPayload = {
  title: string
  type: string
  content?: string
  body?: string
  metadata: {
    [key: string]: string
  }
}

export const createWebsiteContentMutation = (
  siteName: string,
  payload: NewWebsiteContentPayload
): QueryConfig => ({
  url:     `/api/websites/${siteName}/content/`,
  options: {
    method:  "POST",
    headers: {
      "X-CSRFTOKEN": getCookie("csrftoken") || ""
    }
  },
  body:      payload,
  transform: (response: WebsiteContent) => ({
    websiteContentDetails: {
      [response.uuid]: response
    },
    websiteContentListing: response
  }),
  update: {
    websiteContentDetails: (
      prev: WebsiteContentDetails,
      next: WebsiteContentDetails
    ) => ({
      ...prev,
      ...next
    }),
    websiteContentListing: (
      prev: WebsiteContentListing,
      next: WebsiteContent
    ) => {
      prev = prev ?? {}
      const key = contentListingKey(siteName, next.type)
      const oldList: WebsiteContentListItem[] = prev[key] ?? []
      return {
        ...prev,
        // we'll need to sort this once we figure out a preferred order for the content listing
        [key]: [...oldList, next]
      }
    }
  }
})
