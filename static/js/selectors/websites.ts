import { createSelector } from "reselect"
import { memoize } from "lodash"
import { find, propEq } from "ramda"

import { contentListingKey, WebsiteDetails } from "../query-configs/websites"
import { ReduxState } from "../reducers"

import {
  ContentListingParams,
  WebsiteStarter,
  WebsiteContentListItem,
  Website,
  WebsiteContent
} from "../types/websites"

export const getWebsiteDetailCursor = createSelector(
  (state: ReduxState) => state.entities?.websiteDetails ?? {},
  (websiteDetails: WebsiteDetails) =>
    memoize((name: string): Website => websiteDetails[name])
)

export const getWebsiteListingCursor = createSelector(
  (state: ReduxState) => state.entities?.websitesListing ?? {},
  getWebsiteDetailCursor,
  (listing, websiteDetailCursor) =>
    memoize((offset: number) => {
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
    memoize((textId: string) => content[textId])
)

interface WebsiteContentItem {
  count: number | null
  next: string | null
  previous: string | null
  results: WebsiteContentListItem[]
}

export const getWebsiteContentListingCursor = createSelector(
  (state: ReduxState) => state.entities?.websiteContentListing ?? {},
  getWebsiteContentDetailCursor,
  (listing, websiteContentDetailCursor) =>
    memoize(
      (listingParams: ContentListingParams): WebsiteContentItem => {
        const response = listing[contentListingKey(listingParams)] ?? {}
        const uuids: string[] = response?.results ?? []
        const items = uuids.map(websiteContentDetailCursor)

        return {
          ...response,
          results: items
        }
      },
      (listingParams: ContentListingParams): string =>
        contentListingKey(listingParams)
    )
)
