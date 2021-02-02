import { compose, createStore, applyMiddleware } from "redux"
import { createLogger } from "redux-logger"
import { queryMiddleware } from "redux-query"

import { makeRequest } from "./network_interface"
import rootReducer, { ReduxState } from "../reducers"

// Setup middleware
// eslint-disable-next-line @typescript-eslint/explicit-module-boundary-types
export default function configureStore(initialState?: ReduxState) {
  const COMMON_MIDDLEWARE = [
    queryMiddleware(
      makeRequest,
      (state: ReduxState) => state.queries,
      (state: ReduxState) => state.entities
    )
  ]

  // Store factory configuration
  let createStoreWithMiddleware
  if (process.env.NODE_ENV !== "production" && !global._testing) {
    createStoreWithMiddleware = compose(
      applyMiddleware(...COMMON_MIDDLEWARE, createLogger()),
      window.__REDUX_DEVTOOLS_EXTENSION__ ?
        window.__REDUX_DEVTOOLS_EXTENSION__() :
        (f: any) => f
      // @ts-ignore
    )(createStore)
  } else {
    createStoreWithMiddleware = compose(applyMiddleware(...COMMON_MIDDLEWARE))(
      createStore
    )
  }

  const store = createStoreWithMiddleware(rootReducer, initialState)

  if ((module as any).hot) {
    // Enable Webpack hot module replacement for reducers
    (module as any).hot.accept("../reducers", () => {
      // eslint-disable-next-line @typescript-eslint/no-var-requires
      const nextRootReducer = require("../reducers")

      store.replaceReducer(nextRootReducer)
    })
  }

  return store
}
