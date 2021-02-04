import React, { ReactElement } from "react"
import { Route, Router as ReactRouter } from "react-router"
import { Provider } from "react-redux"
import { History } from "history"
import { Store } from "redux"

import App from "./pages/App"

export interface RootProps {
  history: History
  store: Store
}

export default function Root(props: RootProps): ReactElement {
  const { history, store } = props

  return (
    <div>
      <Provider store={store}>
        <ReactRouter history={history}>
          <Route url="/" component={App} />
        </ReactRouter>
      </Provider>
    </div>
  )
}
