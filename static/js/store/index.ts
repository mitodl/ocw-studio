import { ReduxState } from "./rootReducer"
import configureStore, { Store } from "./configureStore"

export const store = configureStore()

export type AppDispatch = typeof store.dispatch
export type SelectorReturn<T> = (state: ReduxState) => T

export { ReduxState, Store }
