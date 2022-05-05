import React from "react"
import { useSelector } from "react-redux"
import { Route, Switch } from "react-router"
import { Link, useRouteMatch } from "react-router-dom"
import { useRequest } from "redux-query-react"

import SitePage from "./SitePage"
import SiteCreationPage from "./SiteCreationPage"
import SitesDashboard from "./SitesDashboard"
import Header from "../components/Header"
import Footer from "../components/Footer"
import HomePage from "./HomePage"
import MarkdownEditorTestPage from "./MarkdownEditorTestPage"
import useTracker from "../hooks/tracker"
import { websiteDetailRequest } from "../query-configs/websites"
import { getWebsiteDetailCursor } from "../selectors/websites"
import WebsiteContext from "../context/Website"
import PrivacyPolicyPage from "./PrivacyPolicyPage"
import NotFound from "../components/NotFound"
import { siteDetailUrl, sitesBaseUrl } from "../lib/urls"
import AuthenticationAlert from "../components/AuthenticationAlert"

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

  const [{ isPending: isSiteLoading, status }] = useRequest(
    siteName ? websiteDetailRequest(siteName) : null
  )
  const website = useSelector(getWebsiteDetailCursor)(siteName || "")

  return (
    <div className="app">
      <div className="app-content">
        <Header website={website} />
        <AuthenticationAlert />
        <div className="page-content">
          <Switch>
            <Route exact path="/" component={HomePage} />
            <Route exact path="/new-site" component={SiteCreationPage} />
            <Route exact path="/sites" component={SitesDashboard} />
            <Route path={siteDetailUrl.pathname}>
              {status === 404 ? (
                <NotFound>
                  <div>
                    We couldn't locate a site named "{siteName}". Try returning
                    to the{" "}
                    <Link to={sitesBaseUrl.toString()} className="underline">
                      site index
                    </Link>
                    . Sorry!
                  </div>
                </NotFound>
              ) : (
                <WebsiteContext.Provider value={website}>
                  <SitePage isLoading={isSiteLoading} />
                </WebsiteContext.Provider>
              )}
            </Route>
            <Route path="/privacy-policy" component={PrivacyPolicyPage} />
            <Route path="/markdown-editor">
              <MarkdownEditorTestPage />
            </Route>
            <Route path="*">
              <NotFound />
            </Route>
          </Switch>
        </div>
      </div>
      <Footer />
    </div>
  )
}
