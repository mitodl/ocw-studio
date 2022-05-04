import { Dispatch } from 'redux'
import { combineReducers, ActionCreator } from "@reduxjs/toolkit"
import { entitiesReducer, queriesReducer, ReduxQueryAction } from "redux-query"
import user from "./user"

const rootReducer = combineReducers({
  entities: entitiesReducer,
  queries:  queriesReducer,
  user:     user.reducer
})
export default rootReducer

type GetActions<T extends Record<string, ActionCreator<any>>> = ReturnType<T[keyof T]>

export type UserAction = GetActions<typeof user.actions>

export type AppDispatch = Dispatch<ReduxQueryAction | UserAction>

export type ReduxState = ReturnType<typeof rootReducer>
