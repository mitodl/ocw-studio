import { compose, createStore, applyMiddleware } from "redux"
import { createLogger } from "redux-logger"
import { queryMiddleware } from "redux-query"

import { makeRequest } from "./network_interface"
import rootReducer, { ReduxState } from "./rootReducer"
import { getQueries, getEntities } from "../lib/redux_query"
import authFailureMiddleware from "./middleware/authFailureMiddleware"

export type Store = ReturnType<typeof configureStore>

// Setup middleware
export default function configureStore(initialState?: ReduxState) {
  const COMMON_MIDDLEWARE = [
    queryMiddleware(makeRequest, getQueries, getEntities),
    authFailureMiddleware
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
    (module as any).hot.accept("./rootReducer", () => {
      // eslint-disable-next-line @typescript-eslint/no-var-requires
      const nextRootReducer = require("./rootReducer")

      store.replaceReducer(nextRootReducer)
    })
  }

  return store
}
