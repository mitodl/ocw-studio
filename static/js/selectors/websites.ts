import { createSelector } from "reselect"
import { memoize } from "lodash"
import { find, propEq } from "ramda"

import { contentListingKey } from "../query-configs/websites"
import { ReduxState } from "../reducers"

import { WebsiteStarter } from "../types/websites"

export const getWebsiteDetailCursor = createSelector(
  (state: ReduxState) => state.entities?.websiteDetails ?? {},
  websiteDetails => memoize((name: string) => websiteDetails[name])
)

export const getWebsiteListingCursor = createSelector(
  (state: ReduxState) => state ?? {},
  state =>
    memoize((offset: number) => {
      const listing = state.entities?.websitesListing ?? {}
      const response = listing[offset] ?? {}
      const names = response?.results ?? []
      const sites = names.map((name: string) =>
        getWebsiteDetailCursor(state)(name)
      )

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

export const getWebsiteContentListingCursor = createSelector(
  (state: ReduxState) => state.entities?.websiteContentListing ?? {},
  listing =>
    memoize(
      (name: string, type: string) => listing[contentListingKey(name, type)],
      (name, type) => `${name}-${type}`
    )
)

export const getWebsiteContentDetailCursor = createSelector(
  (state: ReduxState) => state.entities?.websiteContentDetails ?? {},
  content => memoize((uuid: string) => content[uuid])
)
