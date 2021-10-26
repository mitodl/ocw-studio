import React from "react"
import { useSelector } from "react-redux"
import { Route, Switch } from "react-router"
import { useRouteMatch } from "react-router-dom"
import { useRequest } from "redux-query-react"

import SitePage from "./SitePage"
import SiteCreationPage from "./SiteCreationPage"
import SitesDashboard from "./SitesDashboard"
import Header from "../components/Header"
import Footer from "../components/Footer"
import HomePage from "./HomePage"
import MarkdownEditorTestPage from "./MarkdownEditorTestPage"
import WebsiteCollectionsPage from "./WebsiteCollectionsPage"
import useTracker from "../hooks/tracker"
import { websiteDetailRequest } from "../query-configs/websites"
import { getWebsiteDetailCursor } from "../selectors/websites"
import WebsiteContext from "../context/Website"
import PrivacyPolicyPage from "./PrivacyPolicyPage"

interface SiteMatchParams {
  name: string
}

export default function App(): JSX.Element {
  useTracker()

  let siteName = null
  const siteDetailMatch = useRouteMatch<SiteMatchParams>("/sites/:name")
  if (siteDetailMatch) {
    siteName = siteDetailMatch.params.name
  }

  const [{ isPending: isSiteLoading }] = useRequest(
    siteName ? websiteDetailRequest(siteName) : null
  )
  const website = useSelector(getWebsiteDetailCursor)(siteName || "")

  return (
    <div className="app">
      <div className="app-content">
        <Header website={website} />
        <div className="page-content">
          <Switch>
            <Route exact path="/" component={HomePage} />
            <Route exact path="/new-site" component={SiteCreationPage} />
            <Route exact path="/sites" component={SitesDashboard} />
            <Route path="/sites/:name">
              <WebsiteContext.Provider value={website}>
                <SitePage isLoading={isSiteLoading} />
              </WebsiteContext.Provider>
            </Route>
            <Route path="/collections" component={WebsiteCollectionsPage} />
            <Route path="/privacy-policy" component={PrivacyPolicyPage} />
            <Route path="/markdown-editor">
              <MarkdownEditorTestPage />
            </Route>
          </Switch>
        </div>
      </div>
      <Footer />
    </div>
  )
}
