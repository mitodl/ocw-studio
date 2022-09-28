import React, { ComponentType } from "react"
import ReactDOM from "react-dom"
import { AppContainer } from "react-hot-loader"

import { store } from "./store"
import Root, { RootProps } from "./Root"

import * as Sentry from "@sentry/browser"
import katex from 'katex'

require("react-hot-loader/patch")
/* global SETTINGS:false */
__webpack_public_path__ = SETTINGS.public_path // eslint-disable-line no-undef, camelcase

Sentry.init({
  dsn:         SETTINGS.sentry_dsn,
  release:     SETTINGS.release_version,
  environment: SETTINGS.environment
})

const rootEl = document.getElementById("container")

const renderApp = (Component: ComponentType<RootProps>): void => {
  ReactDOM.render(
    <AppContainer>
      <Component store={store} />
    </AppContainer>,
    rootEl
  )
}

renderApp(Root)

if ((module as any).hot) {
  (module as any).hot.accept("./Root", () => {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const RootNext = require("./Root").default
    renderApp(RootNext)
  })
}
