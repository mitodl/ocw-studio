import { createSelector } from "reselect"
import { memoize } from "lodash"

import { ReduxState } from "../reducers"

export const getWebsiteCursor = createSelector(
  (state: ReduxState) => state.entities?.websites ?? {},
  websites => memoize((name: string) => websites[name])
)
