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
  WebsiteCollaboratorForm,
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
          (value: [WebsiteCollaborator]) => value || []
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
  item: WebsiteCollaboratorForm
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
        prev: [WebsiteCollaborator],
        next: [WebsiteCollaborator]
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
