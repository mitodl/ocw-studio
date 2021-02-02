import React, { ReactElement } from "react"
import { Route, Router as ReactRouter } from "react-router"
import { Provider } from "react-redux"
import { History } from "history"
import { Store } from "redux"

import App from "./containers/App"

import useTracker from "./hooks/tracker"

export interface RootProps {
  history: History
  store: Store
}

export default class Root extends React.Component<RootProps> {
  render(): ReactElement {
    const { history, store } = this.props

    useTracker()

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
}
