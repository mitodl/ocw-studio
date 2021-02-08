import React from "react"
import { Route } from "react-router"

import useTracker from "../hooks/tracker"

export default function App(): JSX.Element {
  useTracker()

  return (
    <div className="app">
      <Route exact path="/" render={() => <div>Hello cookiecutter!</div>} />
    </div>
  )
}
