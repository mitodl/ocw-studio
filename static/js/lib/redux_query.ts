import { getCookie } from "./api/util"
import { ReduxState } from "../reducers"
import { QueriesState, Entities } from "redux-query"

export const DEFAULT_POST_OPTIONS = {
  headers: {
    "X-CSRFTOKEN": getCookie("csrftoken")
  }
}

export const getQueries = (state: ReduxState): QueriesState => state.queries
export const getEntities = (state: ReduxState): Entities => state.entities
