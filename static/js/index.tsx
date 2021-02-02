import React, { ComponentType } from "react"
import ReactDOM from "react-dom"
import { AppContainer } from "react-hot-loader"
import { createBrowserHistory } from "history"

import configureStore from "./store/configureStore"
import Router, { RootProps } from "./Router"

import * as Sentry from "@sentry/browser"

require("react-hot-loader/patch")
/* global SETTINGS:false */
__webpack_public_path__ = SETTINGS.public_path // eslint-disable-line no-undef, camelcase

Sentry.init({
  dsn:         SETTINGS.sentry_dsn,
  release:     SETTINGS.release_version,
  environment: SETTINGS.environment
})

const store = configureStore()

const rootEl = document.getElementById("container")

const renderApp = (Component: ComponentType<RootProps>): void => {
  const history = createBrowserHistory()
  ReactDOM.render(
    <AppContainer>
      <Component history={history} store={store} />
    </AppContainer>,
    rootEl
  )
}

renderApp(Router)

if ((module as any).hot) {
  (module as any).hot.accept("./Router", () => {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const RouterNext = require("./Router").default
    renderApp(RouterNext)
  })
}
