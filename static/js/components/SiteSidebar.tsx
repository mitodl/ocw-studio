import * as React from "react"
import { NavLink } from "react-router-dom"

import { siteContentListingUrl } from "../lib/urls"

import { ConfigItem, Website } from "../types/websites"
import { addToMapList } from "../lib/util"

const buildConfigMap = (website: Website, configItems: ConfigItem[]) => {
  // Create a map with all defined categories mapped to the config items in that category.
  // ex: {"Content": [<config item>, <config item>], "Settings": [<config item>]}
  // Using a Map to maintain the order of insertion for keys.
  const configMap = new Map<string, Array<ConfigItem>>()
  configItems.forEach((configItem: ConfigItem) => {
    addToMapList(configMap, configItem.category, configItem)
  })

  if (website.is_admin) {
    addToMapList(configMap, "Settings", {
      name:     "collaborators",
      label:    "Collaborators",
      category: "Settings",
      fields:   []
    })
  }

  return configMap
}

interface SectionProps {
  category: string
  website: Website
  configItems: ConfigItem[]
  bottomPadding: boolean
}

function SidebarSection(props: SectionProps): JSX.Element {
  const { website, configItems, category, bottomPadding } = props

  const iconName = category === "Settings" ? "settings" : "create"

  const className = bottomPadding ? "sidebar-section pb-4" : "sidebar-section"

  return (
    <div className={className}>
      <h4 className="d-flex align-items-center">
        <i className="material-icons pr-2">{iconName}</i>
        {category}
      </h4>
      {configItems.map((item: ConfigItem) => (
        <NavLink
          key={item.name}
          exact
          className="font-weight-light my-2"
          to={siteContentListingUrl
            .param({ name: website.name, contentType: item.name })
            .toString()}
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

  const configItems: ConfigItem[] = website.starter?.config?.collections ?? []

  const configSections = [...buildConfigMap(website, configItems).entries()]

  return (
    <div className="sidebar">
      <h2 className="pb-5 border-bottom-gray mb-3">OCW Studio</h2>
      {configSections.map(([category, configItems], idx) => (
        <SidebarSection
          category={category}
          key={category}
          website={website}
          configItems={configItems}
          bottomPadding={idx !== configSections.length - 1}
        />
      ))}
    </div>
  )
}
