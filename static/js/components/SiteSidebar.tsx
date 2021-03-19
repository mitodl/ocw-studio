import * as React from "react"
import { NavLink } from "react-router-dom"

import { siteContentListingUrl } from "../lib/urls"

import { ConfigItem, Website } from "../types/websites"
import { addToMapList } from "../lib/util"

interface MenuLink {
  label: string
  name: string
}

type NavMenuItem = ConfigItem | MenuLink

interface Props {
  website: Website
}

const collaboratorMenuItem: MenuLink = {
  name:  "collaborators",
  label: "Collaborators"
}

const renderCategoryConfigs = (
  website: Website,
  configItems: Array<NavMenuItem>
): JSX.Element | null => {
  if (configItems.length === 0) {
    return null
  }
  return (
    <ul>
      {configItems.map((configItem: NavMenuItem) => (
        <li key={configItem.name}>
          <NavLink
            exact
            to={siteContentListingUrl
              .param({
                name:        website.name,
                contentType: configItem.name
              })
              .toString()}
          >
            {configItem.label}
          </NavLink>
        </li>
      ))}
    </ul>
  )
}

export default function SiteSidebar(props: Props): JSX.Element {
  const { website } = props

  const configItems: ConfigItem[] = website.starter?.config?.collections ?? []

  // Create a map with all defined categories mapped to the config items in that category.
  //   ex: {"Content": [<config item>, <config item>], "Settings": [<config item>]}
  // Using a Map to maintain the order of insertion for keys.
  const configMap = new Map<string, Array<ConfigItem>>()
  configItems.forEach((configItem: ConfigItem) => {
    addToMapList(configMap, configItem.category, configItem)
  })
  if (website.is_admin) {
    addToMapList(configMap, "Settings", collaboratorMenuItem)
  }

  return (
    <ul>
      {Array.from(configMap.entries()).map(([category, configItems]) => (
        <li key={category}>
          <span>{category}</span>
          {renderCategoryConfigs(website, configItems)}
        </li>
      ))}
    </ul>
  )
}
