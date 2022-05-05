import { useDispatch, useSelector, TypedUseSelectorHook } from "react-redux"
import { AppDispatch, ReduxState } from "../store"

/**
 * Like `useDispatch` from react-redux, but typed for our app's store.
 */
export const useAppDispatch = (): AppDispatch => useDispatch<AppDispatch>()

/**
 * Like `useSelector` from react-redux, but typed for our app's store.
 */
export const useAppSelector: TypedUseSelectorHook<ReduxState> = useSelector
