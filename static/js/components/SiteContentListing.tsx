import React from "react"
import { useRouteMatch, NavLink } from "react-router-dom"
import { useSelector } from "react-redux"

import { siteContentListingUrl } from "../lib/urls"
import { getWebsiteDetailCursor } from "../selectors/websites"

import { ConfigItem } from "../types/websites"

interface MatchParams {
  configname: string
  name: string
}
export default function SiteContentListing(): JSX.Element | null {
  const match = useRouteMatch<MatchParams>()
  const { configname, name } = match.params
  const website = useSelector(getWebsiteDetailCursor)(name)

  const configItem = website?.starter?.config?.collections.find(
    (config: ConfigItem) => config.name === configname
  )
  if (!configItem) {
    return null
  }

  return (
    <div>
      <h3>
        <NavLink to={siteContentListingUrl(name, configname)}>
          {configItem.label} /
        </NavLink>
      </h3>
    </div>
  )
}
