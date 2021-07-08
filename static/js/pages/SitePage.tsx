import * as React from "react"
import { useSelector } from "react-redux"
import { useMutation, useRequest } from "redux-query-react"
import { Route, Switch, useRouteMatch } from "react-router-dom"

import SiteSidebar from "../components/SiteSidebar"
import SiteContentListing from "../components/SiteContentListing"
import SiteCollaboratorList from "../components/SiteCollaboratorList"
import Card from "../components/Card"

import { websiteAction, websiteDetailRequest } from "../query-configs/websites"
import { getWebsiteDetailCursor } from "../selectors/websites"

interface MatchParams {
  name: string
}

export default function SitePage(): JSX.Element | null {
  const match = useRouteMatch<MatchParams>()
  const { name } = match.params

  const [{ isPending: previewIsPending }, previewWebsite] = useMutation(() =>
    websiteAction(name, "preview")
  )
  const [{ isPending: publishIsPending }, publishWebsite] = useMutation(() =>
    websiteAction(name, "publish")
  )

  const [{ isPending }] = useRequest(websiteDetailRequest(name))
  const website = useSelector(getWebsiteDetailCursor)(name)

  if (!website) {
    return null
  }

  if (isPending) {
    return <div className="site-page std-page-body container">Loading...</div>
  }

  const onPreview = async () => {
    if (previewIsPending) {
      return
    }
    const response = await previewWebsite()
    if (!response) {
      return
    } else {
      // TBD
    }
  }

  const onPublish = async () => {
    if (publishIsPending) {
      return
    }
    const response = await publishWebsite()
    if (!response) {
      return
    } else {
      // TBD
    }
  }

  return (
    <div className="site-page std-page-body container pt-3">
      <div className="content-container">
        <Card>
          <SiteSidebar website={website} />
        </Card>
        <div className="content pl-3">
          <div className="d-flex flex-row justify-content-between">
            <h1 className="py-5 title my-auto">{website.title}</h1>
            <div className="my-auto">
              <button
                type="button"
                onClick={onPreview}
                disabled={previewIsPending}
                className="btn btn-publish green-button-outline"
              >
                Preview
              </button>
              <button
                type="button"
                onClick={onPublish}
                disabled={publishIsPending}
                className="btn btn-publish green-button-outline"
              >
                Publish
              </button>
            </div>
          </div>
          <Switch>
            <Route path={`${match.path}/collaborators/`}>
              <SiteCollaboratorList />
            </Route>
            <Route exact path={`${match.path}/type/:contenttype`}>
              <SiteContentListing />
            </Route>
          </Switch>
        </div>
      </div>
    </div>
  )
}
