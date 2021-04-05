import * as React from "react"
import { useSelector } from "react-redux"
import { useRequest } from "redux-query-react"
import { Route, Switch, useRouteMatch } from "react-router-dom"

import SiteSidebar from "../components/SiteSidebar"
import SiteContentListing from "../components/SiteContentListing"
import SiteCollaboratorList from "../components/SiteCollaboratorList"
import SiteAddContent from "../components/SiteAddContent"
import Card from "../components/Card"

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
    <div className="site-page std-page-body container pt-3">
      <div className="content-container">
        <Card>
          <SiteSidebar website={website} />
        </Card>
        <div className="content pl-3">
          <h3 className="py-5">{website.title}</h3>
          <Switch>
            <Route path={`${match.path}/collaborators/`}>
              <SiteCollaboratorList />
            </Route>
            <Route exact path={`${match.path}/:contenttype`}>
              <SiteContentListing />
            </Route>
            <Route exact path={`${match.path}/:contenttype/add/`}>
              <SiteAddContent />
            </Route>
          </Switch>
        </div>
      </div>
    </div>
  )
}
