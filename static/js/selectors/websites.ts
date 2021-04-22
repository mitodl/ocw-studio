import { createSelector } from "reselect"
import { memoize } from "lodash"
import { find, propEq } from "ramda"

import { contentListingKey } from "../query-configs/websites"
import { ReduxState } from "../reducers"

import { ContentListingParams, WebsiteStarter } from "../types/websites"

export const getWebsiteDetailCursor = createSelector(
  (state: ReduxState) => state.entities?.websiteDetails ?? {},
  websiteDetails => memoize((name: string) => websiteDetails[name])
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
  content => memoize((textId: string) => content[textId])
)

export const getWebsiteContentListingCursor = createSelector(
  (state: ReduxState) => state.entities?.websiteContentListing ?? {},
  getWebsiteContentDetailCursor,
  (listing, websiteContentDetailCursor) =>
    memoize(
      (listingParams: ContentListingParams) => {
        const response = listing[contentListingKey(listingParams)] ?? {}
        const uuids = response?.results ?? []
        const items = uuids.map(websiteContentDetailCursor)

        return {
          ...response,
          results: items
        }
      },
      (listingParams: ContentListingParams) => contentListingKey(listingParams)
    )
)
