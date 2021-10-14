import * as React from "react"
import { NavLink } from "react-router-dom"

import { siteCollaboratorsUrl, siteContentListingUrl } from "../lib/urls"

import { TopLevelConfigItem, Website } from "../types/websites"
import { addToMapList } from "../lib/util"

const collaboratorsConfigName = "_collaborators"

const buildConfigMap = (
  website: Website,
  configItems: TopLevelConfigItem[]
): Map<string, Array<TopLevelConfigItem>> => {
  // Create a map with all defined categories mapped to the config items in that category.
  // ex: {"Content": [<config item>, <config item>], "Settings": [<config item>]}
  // Using a Map to maintain the order of insertion for keys.
  const adminOnlyItems = ["metadata"]
  const configMap = new Map<string, Array<TopLevelConfigItem>>()
  configItems.forEach((configItem: TopLevelConfigItem) => {
    if (website.is_admin || !adminOnlyItems.includes(configItem.name)) {
      addToMapList(configMap, configItem.category, configItem)
    }
  })

  if (website.is_admin) {
    addToMapList(configMap, "Settings", {
      name:     collaboratorsConfigName,
      label:    "Collaborators",
      category: "Settings",
      fields:   [],
      folder:   ""
    })
  }

  return configMap
}

interface SectionProps {
  category: string
  website: Website
  configItems: TopLevelConfigItem[]
  bottomPadding: boolean
}

function SidebarSection(props: SectionProps): JSX.Element {
  const { website, configItems, category, bottomPadding } = props

  const iconName = category === "Settings" ? "settings" : "create"

  const className = bottomPadding ? "sidebar-section pb-4" : "sidebar-section"

  return (
    <div className={className}>
      <h4 className="d-flex font-weight-bold align-items-center">
        <i className="material-icons pr-2">{iconName}</i>
        {category}
      </h4>
      {configItems.map((item: TopLevelConfigItem) => (
        <NavLink
          key={item.name}
          exact
          className="font-weight-light my-2"
          to={
            item.name === collaboratorsConfigName ?
              siteCollaboratorsUrl.param({ name: website.name }).toString() :
              siteContentListingUrl
                .param({ name: website.name, contentType: item.name })
                .toString()
          }
        >
          {item.label}
        </NavLink>
      ))}
    </div>
  )
}

interface Props {
  website: Website
}

export default function SiteSidebar(props: Props): JSX.Element {
  const { website } = props

  const configItems: TopLevelConfigItem[] =
    website.starter?.config?.collections ?? []

  const configSections = [...buildConfigMap(website, configItems).entries()]

  return (
    <div className="sidebar">
      <h2 className="pb-5 border-bottom-gray mb-3">OCW Studio</h2>
      {configSections.map(([category, configItems], idx) => (
        <SidebarSection
          key={idx}
          category={category}
          website={website}
          configItems={configItems}
          bottomPadding={idx !== configSections.length - 1}
        />
      ))}
    </div>
  )
}
