import { getCookie } from "./api/util"

export const DEFAULT_POST_OPTIONS = {
  headers: {
    "X-CSRFTOKEN": getCookie("csrftoken")
  }
}

export const getQueries = state => state.queries
export const getEntities = state => state.entities
