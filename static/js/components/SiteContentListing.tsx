import React from "react"
import { useRouteMatch } from "react-router-dom"
import pluralize from "pluralize"
import { capitalize, words } from "lodash"

import RepeatableContentListing from "./RepeatableContentListing"
import SingletonsContentListing from "./SingletonsContentListing"

import {
  addDefaultFields,
  isRepeatableCollectionItem
} from "../lib/site_content"
import { useWebsite } from "../context/Website"

import { TopLevelConfigItem } from "../types/websites"
import DocumentTitle, { formatTitle } from "./DocumentTitle"

interface MatchParams {
  contenttype: string
  name: string
}

export const repeatableTitle = (contenttype: string): string =>
  pluralize(singletonTitle(contenttype))

export const singletonTitle = (contenttype: string): string =>
  words(contenttype)
    .map(capitalize)
    .join(" ")

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
    <>
      <RepeatableContentListing configItem={addDefaultFields(configItem)} />
      <DocumentTitle
        title={formatTitle(website.title, repeatableTitle(contenttype))}
      />
    </>
  ) : (
    <>
      <SingletonsContentListing configItem={configItem} />
      <DocumentTitle
        title={formatTitle(website.title, singletonTitle(contenttype))}
      />
    </>
  )
}
