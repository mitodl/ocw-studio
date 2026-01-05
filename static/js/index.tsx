import React, { ComponentType } from "react"
import { createRoot, Root } from "react-dom/client"
import { AppContainer } from "react-hot-loader"

import { store } from "./store"
import RootComponent, { RootProps } from "./Root"

import * as Sentry from "@sentry/react"

require("react-hot-loader/patch")
/* global SETTINGS:false */
__webpack_public_path__ = SETTINGS.public_path // eslint-disable-line no-undef, camelcase

Sentry.init({
  dsn: SETTINGS.sentry_dsn,
  release: SETTINGS.release_version,
  environment: SETTINGS.environment,
})

const rootEl = document.getElementById("container")
if (!rootEl) {
  throw new Error("Root element not found")
}
const root: Root = createRoot(rootEl)

const renderApp = (Component: ComponentType<RootProps>): void => {
  root.render(
    <AppContainer>
      <Component store={store} />
    </AppContainer>,
  )
}

renderApp(RootComponent)

if ((module as any).hot) {
  ;(module as any).hot.accept("./Root", () => {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const RootNext = require("./Root").default
    renderApp(RootNext)
  })
}
