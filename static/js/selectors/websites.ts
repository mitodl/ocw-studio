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
  listing => (name: string, type: string) =>
    // not memoized since there are two arguments
    listing[contentListingKey(name, type)]
)

export const getWebsiteContentDetailCursor = createSelector(
  (state: ReduxState) => state.entities?.websiteContentDetails ?? {},
  content => memoize((uuid: string) => content[uuid])
)
