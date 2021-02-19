import { combineReducers } from "redux"
import { entitiesReducer, queriesReducer } from "redux-query"

const rootReducer = combineReducers({
  entities: entitiesReducer,
  queries:  queriesReducer
})
export default rootReducer

export type ReduxState = ReturnType<typeof rootReducer>
