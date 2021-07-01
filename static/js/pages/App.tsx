import React from "react"
import { Route, Switch } from "react-router"

import SitePage from "./SitePage"
import SiteCreationPage from "./SiteCreationPage"
import SitesDashboard from "./SitesDashboard"
import Header from "../components/Header"
import HomePage from "./HomePage"
import MarkdownEditorTestPage from "./MarkdownEditorTestPage"
import WebsiteCollectionsPage from "./WebsiteCollectionsPage"
import useTracker from "../hooks/tracker"

export default function App(): JSX.Element {
  useTracker()

  return (
    <div className="app">
      <Route
        path={["/", "/new-site", "/sites", "/markdown-editor", "/collections"]}
        exact
      >
        <Header />
      </Route>
      <div className="page-content">
        <Switch>
          <Route exact path="/" component={HomePage} />
          <Route exact path="/new-site" component={SiteCreationPage} />
          <Route exact path="/sites" component={SitesDashboard} />
          <Route path="/sites/:name" component={SitePage} />
          <Route path="/collections" component={WebsiteCollectionsPage} />
          <Route path="/markdown-editor">
            <MarkdownEditorTestPage />
          </Route>
        </Switch>
      </div>
    </div>
  )
}
