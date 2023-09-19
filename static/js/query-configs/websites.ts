import { ActionPromiseValue, QueryConfig } from "redux-query"
import { mergeDeepRight } from "ramda"

import { nextState, PaginatedResponse } from "./utils"
import { getCookie } from "../lib/api/util"
import { DEFAULT_POST_OPTIONS } from "../lib/redux_query"
import {
  siteApi,
  startersApi,
  siteApiCollaboratorsDetailUrl,
  siteApiCollaboratorsUrl,
  siteApiListingUrl,
  siteApiDetailUrl,
  siteApiActionUrl,
  siteApiUnpublishUrl,
  siteApiContentListingUrl,
  siteApiContentDetailUrl,
  siteApiContentUrl,
  siteApiContentSyncGDriveUrl,
} from "../lib/urls"

import {
  CollaboratorDetailParams,
  CollaboratorListingParams,
  ContentDetailParams,
  ContentListingParams,
  NewWebsitePayload,
  Website,
  WebsiteCollaborator,
  WebsiteCollaboratorFormData,
  WebsiteContent,
  WebsiteContentListItem,
  WebsiteStarter,
  WebsiteStatus,
} from "../types/websites"
import { PublishingEnv } from "../constants"

export type WebsiteDetails = Record<string, Website>

export const getTransformedWebsiteName = (
  response: ActionPromiseValue<Record<string, WebsiteDetails>>,
): string | null => {
  const transformedWebsiteKeys = Object.keys(
    response.transformed?.websiteDetails || {},
  )
  if (transformedWebsiteKeys.length === 0) {
    return null
  }
  return transformedWebsiteKeys[0]
}

export type WebsiteListingParams = {
  offset: number
  search?: string | null | undefined
  published?: boolean
}

export type WebsiteListingResponse = PaginatedResponse<Website>

export type WebsitesListing = Record<string, PaginatedResponse<string>>

export const websiteListingRequest = (
  params: WebsiteListingParams,
): QueryConfig => ({
  url: siteApiListingUrl.query(params).toString(),
  transform: (body: WebsiteListingResponse) => {
    const details = {}
    for (const site of body.results) {
      details[site.name] = site
    }

    return {
      websitesListing: {
        [params.offset]: {
          ...body,
          results: body.results.map((result) => result.name),
        },
      },
      websiteDetails: details,
    }
  },
  update: {
    websitesListing: (prev: WebsitesListing, next: WebsitesListing) => ({
      ...prev,
      ...next,
    }),
    websiteDetails: (prev: WebsiteDetails, next: WebsiteDetails) => ({
      ...prev,
      ...next,
    }),
  },
  force: true, // try to prevent stale information
})

export const websiteDetailRequest = (name: string): QueryConfig => ({
  url: siteApiDetailUrl.param({ name }).toString(),
  transform: (body: Website) => ({
    websiteDetails: {
      [name]: body,
    },
  }),
  update: {
    websiteDetails: (prev: WebsiteDetails, next: WebsiteDetails) => ({
      ...prev,
      ...next,
    }),
  },
  force: true, // force a refresh to update incomplete information from listing API
})

export const websiteStatusRequest = (name: string): QueryConfig => ({
  queryKey: `publish-status-${name}`,
  url: siteApiDetailUrl.param({ name }).query({ only_status: true }).toString(),
  transform: (body: WebsiteStatus) => ({
    websiteDetails: body,
  }),
  update: {
    websiteDetails: (prev: WebsiteDetails, next: WebsiteStatus) => ({
      ...prev,
      [name]: {
        ...(prev[name] ?? {}),
        ...next,
      },
    }),
  },
  force: true,
})

export const websiteMutation = (payload: NewWebsitePayload): QueryConfig => ({
  url: siteApi.toString(),
  options: {
    method: "POST",
    headers: {
      "X-CSRFTOKEN": getCookie("csrftoken") || "",
    },
  },
  body: payload,
  transform: (body: Website) => ({
    websiteDetails: {
      [body.name]: body,
      [body.short_id]: body,
    },
  }),
  update: {
    websiteDetails: (prev: WebsiteDetails, next: WebsiteDetails) => ({
      ...prev,
      ...next,
    }),
  },
})

export const websitePublishAction = (
  name: string,
  publishingEnv: PublishingEnv,
  payload: WebsitePublishPayload,
): QueryConfig => {
  const action =
    publishingEnv === PublishingEnv.Production ? "publish" : "preview"
  return {
    url: siteApiActionUrl.param({ name, action }).toString(),
    options: {
      method: "POST",
      headers: {
        "X-CSRFTOKEN": getCookie("csrftoken") || "",
      },
    },
    body: payload,
  }
}

export const websiteUnpublishAction = (
  name: string,
  method: string,
): QueryConfig => {
  return {
    url: siteApiUnpublishUrl.param({ name }).toString(),
    options: {
      method: method,
      headers: {
        "X-CSRFTOKEN": getCookie("csrftoken") || "",
      },
    },
  }
}

export const websiteStartersRequest = (): QueryConfig => ({
  url: startersApi.toString(),
  transform: (results: Array<WebsiteStarter>) => ({
    starters: results,
  }),
  update: {
    starters: nextState,
  },
})

export const deleteWebsiteCollaboratorMutation = (
  websiteName: string,
  collaborator: WebsiteCollaborator,
): QueryConfig => {
  return {
    queryKey: "deleteWebsiteCollaboratorMutation",
    url: siteApiCollaboratorsDetailUrl
      .param({
        name: websiteName,
        userId: collaborator.user_id,
      })
      .toString(),
    options: {
      method: "DELETE",
      ...DEFAULT_POST_OPTIONS,
    },
  }
}

export const editWebsiteCollaboratorMutation = (
  websiteName: string,
  collaborator: WebsiteCollaborator,
  role: string,
): QueryConfig => {
  return {
    queryKey: "editWebsiteCollaboratorMutation",
    body: { role },
    url: siteApiCollaboratorsDetailUrl
      .param({
        name: websiteName,
        userId: collaborator.user_id,
      })
      .toString(),
    options: {
      method: "PATCH",
      ...DEFAULT_POST_OPTIONS,
    },
  }
}

export const createWebsiteCollaboratorMutation = (
  websiteName: string,
  item: WebsiteCollaboratorFormData,
): QueryConfig => {
  return {
    queryKey: "editWebsiteCollaboratorMutation",
    body: { ...item },
    url: siteApiCollaboratorsUrl.param({ name: websiteName }).toString(),
    options: {
      method: "POST",
      ...DEFAULT_POST_OPTIONS,
    },
  }
}

export type WebsiteContentListingResponse = PaginatedResponse<
  WebsiteContentListItem | WebsiteContent
>

export type WebsiteCollaboratorListingResponse =
  PaginatedResponse<WebsiteCollaborator>

export const collaboratorDetailKey = (
  params: CollaboratorDetailParams,
): string => JSON.stringify([params.name, params.userId])

export type WebsiteContentListing = Record<
  string,
  {
    results: string[]
    count: number | null
    next: string | null
    previous: string | null
  }
>
export type WebsiteCollaboratorListing = Record<
  string,
  {
    results: string[]
    count: number | null
    next: string | null
    previous: string | null
  }
>
export const contentListingKey = (
  listingParams: ContentListingParams,
): string =>
  JSON.stringify([
    listingParams.name,
    listingParams.type,
    listingParams.search,
    listingParams.pageContent,
    listingParams.offset,
    listingParams.resourcetype,
    listingParams.published,
  ])

export const collaboratorListingKey = (
  listingParams: CollaboratorListingParams,
): string => JSON.stringify([listingParams.name, listingParams.offset])
export const contentDetailKey = (params: ContentDetailParams): string =>
  JSON.stringify([params.name, params.textId])

/**
 * Query config for fetching the content items for a website.
 *
 * Pass the `requestDetailedList` param if you need to get the detailed view of
 * all the content items, as opposed to a minimal, summary view of the items
 * (requestDetailedList == true tells the backend to use the
 * WebsiteContentDetailSerializer as opposed to the WebsiteContentSerializer,
 * the default for this view).
 **/
export const websiteContentListingRequest = (
  listingParams: ContentListingParams,
  requestDetailedList: boolean,
  requestContentContext: boolean,
): QueryConfig => {
  const { name, type, resourcetype, offset, pageContent, search, published } =
    listingParams
  const url = siteApiContentListingUrl
    .param({ name })
    .query(
      Object.assign(
        { offset },
        type && { type },
        pageContent && { page_content: pageContent },
        requestDetailedList && { detailed_list: true },
        requestContentContext && { content_context: true },
        search && { search },
        resourcetype && { resourcetype },
        published && { published },
      ),
    )
    .toString()
  return {
    url,
    transform: (body: WebsiteContentListingResponse) => {
      const details = {}
      for (const item of body.results) {
        details[contentDetailKey({ textId: item.text_id, name })] = item
      }
      return {
        websiteContentListing: {
          [contentListingKey(listingParams)]: {
            ...body,
            results: body.results.map((item) => item.text_id),
          },
        },
        websiteContentDetails: details,
      }
    },
    update: {
      websiteContentListing: (
        prev: WebsiteContentListing,
        next: WebsiteContentListing,
      ) => ({
        ...prev,
        ...next,
      }),
      websiteContentDetails: mergeDeepRight,
    },
    force: true, // try to prevent stale information
  }
}

export const websiteCollaboratorListingRequest = (
  listingParams: CollaboratorListingParams,
): QueryConfig => {
  const { name, offset } = listingParams
  const url = siteApiCollaboratorsUrl
    .param({ name })
    .query(Object.assign({ offset }))
    .toString()
  return {
    url,
    transform: (body: WebsiteCollaboratorListingResponse) => {
      if (body && Array.isArray(body.results)) {
        return {
          collaborators: {
            [collaboratorListingKey(listingParams)]: {
              ...body,
              results: body.results,
            },
          },
        }
      } else {
        return []
      }
    },
    update: {
      collaborators: (
        prev: WebsiteCollaboratorListing,
        next: WebsiteCollaboratorListing,
      ) => ({
        ...prev,
        ...next,
      }),
    },
    force: true, // try to prevent stale information
  }
}

type WebsiteContentDetails = Record<string, WebsiteContent>
export const websiteContentDetailRequest = (
  params: ContentDetailParams,
  requestContentContext: boolean,
): QueryConfig => ({
  url: siteApiContentDetailUrl
    .param({ name: params.name, textId: params.textId })
    .query(requestContentContext ? { content_context: true } : {})
    .toString(),
  transform: (body: WebsiteContent) => ({
    websiteContentDetails: {
      [contentDetailKey(params)]: body,
    },
  }),
  update: {
    websiteContentListing: (
      prev: WebsiteContentListing,
      next: WebsiteContentListing,
    ) => ({
      ...prev,
      ...next,
    }),
    websiteContentDetails: (
      prev: WebsiteContentDetails,
      next: WebsiteContentDetails,
    ) => {
      return {
        ...prev,
        ...next,
      }
    },
  },
  force: true, // some data may be fetched in the collection view which is incomplete
})

export type EditWebsiteContentPayload = {
  title?: string
  content?: string
  body?: string
  metadata?: any
  file?: File
}

export const editWebsiteContentMutation = (
  params: ContentDetailParams,
  payload: EditWebsiteContentPayload | FormData,
): QueryConfig => ({
  url: siteApiContentDetailUrl
    .param({ name: params.name, textId: params.textId })
    .toString(),
  options: {
    method: "PATCH",
    headers: {
      "X-CSRFTOKEN": getCookie("csrftoken") || "",
    },
  },
  body: payload,
  transform: (response: WebsiteContent) => ({
    websiteContentDetails: {
      [contentDetailKey(params)]: response,
    },
  }),
  update: {
    websiteContentDetails: (
      prev: WebsiteContentDetails,
      next: WebsiteContentDetails,
    ) => ({
      ...prev,
      ...next,
    }),
  },
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

export type WebsitePublishPayload = {
  // eslint-disable-next-line camelcase
  url_path?: string
}

export const createWebsiteContentMutation = (
  siteName: string,
  payload: NewWebsiteContentPayload,
): QueryConfig => ({
  url: siteApiContentUrl.param({ name: siteName }).toString(),
  options: {
    method: "POST",
    headers: {
      "X-CSRFTOKEN": getCookie("csrftoken") || "",
    },
  },
  body: payload,
  transform: (response: WebsiteContent) => ({
    websiteContentDetails: {
      [contentDetailKey({ textId: response.text_id, name: siteName })]:
        response,
    },
  }),
  update: {
    websiteContentDetails: (
      prev: WebsiteContentDetails,
      next: WebsiteContentDetails,
    ) => ({
      ...prev,
      ...next,
    }),
  },
})

export const syncWebsiteContentMutation = (siteName: string): QueryConfig => ({
  url: siteApiContentSyncGDriveUrl.param({ name: siteName }).toString(),
  options: {
    method: "POST",
    headers: {
      "X-CSRFTOKEN": getCookie("csrftoken") || "",
    },
  },
  body: {},
})
