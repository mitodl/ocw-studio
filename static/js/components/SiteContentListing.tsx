import React from "react"
import { useRouteMatch } from "react-router-dom"
import { useSelector } from "react-redux"

import RepeatableContentListing from "./RepeatableContentListing"
import SingletonsContentListing from "./SingletonsContentListing"

import {
  addDefaultFields,
  isRepeatableCollectionItem
} from "../lib/site_content"
import { getWebsiteDetailCursor } from "../selectors/websites"
import WebsiteContext from "../context/Website"

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

  return (
    <WebsiteContext.Provider value={website}>
      {isRepeatableCollectionItem(configItem) ? (
        <RepeatableContentListing configItem={addDefaultFields(configItem)} />
      ) : (
        <SingletonsContentListing configItem={configItem} />
      )}
    </WebsiteContext.Provider>
  )
}
