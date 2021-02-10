import { QueriesState, Entities } from "redux-query"
import { combineReducers } from "redux"
import { entitiesReducer, queriesReducer } from "redux-query"

export interface ReduxState {
  queries: QueriesState
  entities: Entities
}

export default combineReducers({
  entities: entitiesReducer,
  queries:  queriesReducer
})
