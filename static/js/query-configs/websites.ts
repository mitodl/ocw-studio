import { ActionPromiseValue, QueryConfig } from "redux-query"

import { nextState } from "./utils"
import { getCookie } from "../lib/api/util"

import { Website, WebsiteStarter, NewWebsitePayload } from "../types/websites"

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
  url:       `/api/websites/${name}/`,
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
