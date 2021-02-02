import React, { ReactElement } from "react"
import { Route } from "react-router"

export default class App extends React.Component {
  render(): ReactElement {
    return (
      <div className="app">
        <Route path="/" render={() => <div>Hello cookiecutter!</div>} />
      </div>
    )
  }
}
