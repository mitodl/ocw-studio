import { combineReducers } from "@reduxjs/toolkit"
import { entitiesReducer, queriesReducer } from "redux-query"
import user from "./user"

const rootReducer = combineReducers({
  entities: entitiesReducer,
  queries:  queriesReducer,
  user:     user.reducer
})
export default rootReducer

export type ReduxState = ReturnType<typeof rootReducer>
