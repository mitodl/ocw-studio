import { createSelector } from "reselect"
import { memoize } from "lodash"

import { ReduxState } from "../reducers"

import { WebsiteStarter } from "../types/websites"

export const getWebsiteDetailCursor = createSelector(
  (state: ReduxState) => state.entities?.websiteDetails ?? {},
  websiteDetails => memoize((name: string) => websiteDetails[name])
)

export const startersSelector = (state: ReduxState): Array<WebsiteStarter> =>
  state.entities?.starters ?? []
