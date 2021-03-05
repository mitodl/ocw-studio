import * as React from "react"
import { useSelector } from "react-redux"
import { useRequest } from "redux-query-react"
import { Route, Switch, useRouteMatch } from "react-router-dom"

import SiteSidebar from "../components/SiteSidebar"
import SiteContentListing from "../components/SiteContentListing"
import SiteCollaboratorList from "../components/SiteCollaboratorList"
import SiteCollaboratorEditPanel from "../components/SiteCollaboratorEditPanel"
import SiteCollaboratorAddPanel from "../components/SiteCollaboratorAddPanel"

import { websiteDetailRequest } from "../query-configs/websites"
import { getWebsiteDetailCursor } from "../selectors/websites"

interface MatchParams {
  name: string
}
export default function SitePage(): JSX.Element | null {
  const match = useRouteMatch<MatchParams>()
  const { name } = match.params
  const [{ isPending }] = useRequest(websiteDetailRequest(name))
  const website = useSelector(getWebsiteDetailCursor)(name)
  if (!website) {
    return null
  }

  if (isPending) {
    return <div className="site-page std-page-body container">Loading...</div>
  }

  return (
    <div className="site-page std-page-body container">
      <h3>{website.title}</h3>
      <div className="content-container">
        <div className="sidebar">
          <SiteSidebar website={website} />
        </div>
        <div className="content">
          <Switch>
            <Route
              path={`${match.path}/settings/collaborators/new/`}
              component={SiteCollaboratorAddPanel}
            />
            <Route
              path={`${match.path}/settings/collaborators/:username/`}
              component={SiteCollaboratorEditPanel}
            />
            <Route
              path={`${match.path}/settings/collaborators/`}
              component={SiteCollaboratorList}
            />
            <Route
              path={`${match.path}/:configname`}
              component={SiteContentListing}
            />
          </Switch>
        </div>
      </div>
    </div>
  )
}
