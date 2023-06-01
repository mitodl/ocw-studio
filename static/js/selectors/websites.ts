import { createSelector } from "reselect"
import { memoize } from "lodash"
import { find, propEq } from "ramda"

import {
  contentDetailKey,
  contentListingKey,
  WebsiteDetails,
  WebsiteListingResponse,
  WebsitesListing
} from "../query-configs/websites"
import { ReduxState } from "../store"
import {
  ContentListingParams,
  WebsiteStarter,
  WebsiteContentListItem,
  Website,
  WebsiteContent,
  ContentDetailParams
} from "../types/websites"

export const getWebsiteDetailCursor = createSelector(
  (state: ReduxState) => state.entities?.websiteDetails ?? {},
  (websiteDetails: WebsiteDetails) =>
    memoize((name: string): Website => websiteDetails[name])
)

type DetailCursor = ReturnType<typeof getWebsiteDetailCursor>

export const getWebsiteListingCursor = createSelector(
  (state: ReduxState) => state.entities?.websitesListing ?? {},
  getWebsiteDetailCursor,
  (listing: WebsitesListing, websiteDetailCursor: DetailCursor) =>
    memoize((offset: number): WebsiteListingResponse => {
      const response = listing[offset] ?? {}
      const names = response?.results ?? []
      const sites = names.map(websiteDetailCursor)

      return {
        ...response,
        results: sites
      }
    })
)

export const startersSelector = (state: ReduxState): Array<WebsiteStarter> =>
  state.entities?.starters ?? []

export const getWebsiteCollaboratorsCursor = createSelector(
  (state: ReduxState) => state.entities?.collaborators ?? {},
  collaborators => memoize((name: string) => collaborators[name])
)

export const getWebsiteCollaboratorDetailCursor = createSelector(
  (state: ReduxState) => state.entities?.collaborators ?? {},
  collaborators =>
    memoize((name: string, username: string) =>
      find(propEq("username", username), collaborators[name])
    )
)

export const getWebsiteContentDetailCursor = createSelector(
  (state: ReduxState) => state.entities?.websiteContentDetails ?? {},
  (content: Record<string, WebsiteContent>) =>
    memoize(
      (params: ContentDetailParams): WebsiteContent | null =>
        content[contentDetailKey(params)] ?? null
    )
)

export interface WCSelection {
  count: number | null
  next: string | null
  previous: string | null
}

export interface WebsiteContentSelection extends WCSelection {
  results: WebsiteContent[]
}

export interface WebsiteContentListSelection extends WCSelection {
  results: WebsiteContentListItem[]
}

export const getWebsiteContentListingCursor = createSelector(
  (state: ReduxState) => state.entities?.websiteContentListing ?? {},
  getWebsiteContentDetailCursor,
  (listing, websiteContentDetailCursor) =>
    memoize(
      (
        listingParams: ContentListingParams
      ): WebsiteContentSelection | WebsiteContentListSelection => {
        const response = listing[contentListingKey(listingParams)] ?? {}
        const uuids: string[] = response?.results ?? []
        const items = uuids.map(uuid =>
          websiteContentDetailCursor({ name: listingParams.name, textId: uuid })
        )

        return {
          ...response,
          results: items
        }
      },
      (listingParams: ContentListingParams): string =>
        contentListingKey(listingParams)
    )
)
