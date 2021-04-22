import React from "react"
import { useRouteMatch } from "react-router-dom"
import { useSelector } from "react-redux"

import RepeatableContentListing from "./RepeatableContentListing"
import SingletonsContentListing from "./SingletonsContentListing"

import { isRepeatableCollectionItem } from "../lib/site_content"
import { getWebsiteDetailCursor } from "../selectors/websites"

import { TopLevelConfigItem } from "../types/websites"

interface MatchParams {
  contenttype: string
  name: string
}

export default function SiteContentListing(): JSX.Element | null {
  const match = useRouteMatch<MatchParams>()
  const { contenttype, name } = match.params

  const website = useSelector(getWebsiteDetailCursor)(name)
  const configItem = website?.starter?.config?.collections.find(
    (config: TopLevelConfigItem) => config.name === contenttype
  )
  if (!configItem) {
    return null
  }

  if (isRepeatableCollectionItem(configItem)) {
    return (
      <RepeatableContentListing website={website} configItem={configItem} />
    )
  }
  return <SingletonsContentListing website={website} configItem={configItem} />
}
