import { ReduxState, AppDispatch } from "./rootReducer"
import configureStore, { Store } from "./configureStore"

export const store = configureStore()

export type SelectorReturn<T> = (state: ReduxState) => T

export { ReduxState, AppDispatch, Store }
