import * as React from "react"
import { Route, Switch } from "react-router-dom"

import SiteSidebar from "../components/SiteSidebar"
import SiteContentListing from "../components/SiteContentListing"
import SiteCollaboratorList from "../components/SiteCollaboratorList"
import Card from "../components/Card"
import { siteCollaboratorsUrl, siteDetailUrl } from "../lib/urls"

import { useWebsite } from "../context/Website"

interface SitePageProps {
  isLoading: boolean
}

export default function SitePage(props: SitePageProps): JSX.Element | null {
  const { isLoading } = props

  const website = useWebsite()

  if (isLoading) {
    return <div className="site-page std-page-body container">Loading...</div>
  }
  if (!website) {
    return null
  }

  return (
    <div className="site-page std-page-body container pt-3">
      <div className="content-container">
        <Card>
          <SiteSidebar website={website} />
        </Card>
        <div className="content pl-3">
          <Switch>
            <Route
              path={siteCollaboratorsUrl.param("name", website.name).toString()}
            >
              <SiteCollaboratorList />
            </Route>
            <Route
              exact
              path={`${siteDetailUrl.param(
                "name",
                website.name
              )}type/:contenttype`}
            >
              <SiteContentListing />
            </Route>
          </Switch>
        </div>
      </div>
    </div>
  )
}
