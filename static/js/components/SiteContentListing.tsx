import React from "react"
import { useRouteMatch } from "react-router-dom"

import RepeatableContentListing from "./RepeatableContentListing"
import SingletonsContentListing from "./SingletonsContentListing"

import {
  addDefaultFields,
  isRepeatableCollectionItem
} from "../lib/site_content"
import { useWebsite } from "../context/Website"

import { TopLevelConfigItem } from "../types/websites"

interface MatchParams {
  contenttype: string
  name: string
}

export default function SiteContentListing(): JSX.Element | null {
  const website = useWebsite()

  const match = useRouteMatch<MatchParams>()
  const { contenttype } = match.params

  const configItem = website?.starter?.config?.collections.find(
    (config: TopLevelConfigItem) => config.name === contenttype
  )
  if (!configItem) {
    return null
  }

  return isRepeatableCollectionItem(configItem) ? (
    <RepeatableContentListing configItem={addDefaultFields(configItem)} />
  ) : (
    <SingletonsContentListing configItem={configItem} />
  )
}
