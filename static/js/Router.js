import React from "react"
import { Route, Router as ReactRouter } from "react-router"
import { Provider } from "react-redux"

import App from "./containers/App"
import withTracker from "./util/withTracker"

export default class Root extends React.Component {
  render() {
    const { children, history, store } = this.props

    return (
      <div>
        <Provider store={store}>
          <ReactRouter history={history}>{children}</ReactRouter>
        </Provider>
      </div>
    )
  }
}

export const routes = <Route url="/" component={withTracker(App)} />
