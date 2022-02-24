import React from "react"
import { Route } from "react-router-dom"

import SiteSidebar from "../components/SiteSidebar"
import SiteContentListing from "../components/SiteContentListing"
import SiteCollaboratorList from "../components/SiteCollaboratorList"
import Card from "../components/Card"
import {
  siteCollaboratorsUrl,
  siteContentListingUrl,
  siteDetailUrl
} from "../lib/urls"

import { useWebsite } from "../context/Website"
import DocumentTitle, { formatTitle } from "../components/DocumentTitle"

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
          <Route
            path={siteCollaboratorsUrl.param("name", website.name).toString()}
          >
            <SiteCollaboratorList />
          </Route>
          <Route
            path={siteContentListingUrl.param({ name: website.name }).pathname}
          >
            <SiteContentListing />
          </Route>
          <Route path={siteDetailUrl.param({ name: website.name }).toString()}>
            <DocumentTitle title={formatTitle(website.title)} />
          </Route>
        </div>
      </div>
    </div>
  )
}
