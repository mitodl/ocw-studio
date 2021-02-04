import React, { ReactElement } from "react"
import { Route } from "react-router"

import useTracker from "../hooks/tracker"

export default function App(): ReactElement {
  useTracker()

  return (
    <div className="app">
      <Route path="/" render={() => <div>Hello cookiecutter!</div>} />
    </div>
  )
}
