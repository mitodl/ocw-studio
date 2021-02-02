import { AnyAction } from "redux"
import { QueriesState, Entities } from "redux-query"

export interface ReduxState {
  queries: QueriesState
  entities: Entities
}

// the minimal reducer is the identity function
// when we implement our own reducers this will be replaced with a call
// to redux's `combineReducers` utility function
export default function(
  state: ReduxState | undefined,
  _: AnyAction
): ReduxState {
  return state || { queries: {}, entities: {} }
}
