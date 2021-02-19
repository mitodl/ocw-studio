import * as React from "react"
import { useSelector } from "react-redux"
import { useRequest } from "redux-query-react"
import { Route, Switch, useRouteMatch } from "react-router-dom"

import SiteSidebar from "../components/SiteSidebar"
import SiteComponent from "../components/SiteComponent"

import { websitesRequest } from "../query-configs/websites"
import { getWebsiteCursor } from "../selectors/websites"

interface MatchParams {
  name: string
}
export default function SitePage(): JSX.Element | null {
  const match = useRouteMatch<MatchParams>()
  const { name } = match.params
  const [{ isPending }] = useRequest(websitesRequest(name))
  const website = useSelector(getWebsiteCursor)(name)
  if (!website) {
    return null
  }

  if (isPending) {
    return <div className="site-page container">Loading...</div>
  }

  return (
    <div className="site-page container">
      <div className="site-page-header">
        <h3>{website.title}</h3>
      </div>
      <div className="row">
        <div className="col-3">
          <SiteSidebar website={website} />
        </div>
        <div className="content col-9">
          <Switch>
            <Route
              path={`${match.path}/:configname`}
              component={SiteComponent}
            />
          </Switch>
        </div>
      </div>
    </div>
  )
}
