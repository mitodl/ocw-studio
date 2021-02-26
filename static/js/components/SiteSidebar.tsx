import * as React from "react"
import { NavLink } from "react-router-dom"

import { siteContentListingUrl } from "../lib/urls"

import { ConfigItem, Website } from "../types/websites"

interface Props {
  website: Website
}
export default function SiteSidebar(props: Props): JSX.Element {
  const { website } = props

  const configItems: ConfigItem[] = website.starter?.config?.collections ?? []

  return (
    <ul>
      {configItems.map(item => (
        <li key={item.name}>
          <NavLink exact to={siteContentListingUrl(website.name, item.name)}>
            {item.label}
          </NavLink>
        </li>
      ))}
      <li>
        Settings
        <ul>
          <li>Collaborators</li>
        </ul>
      </li>
    </ul>
  )
}
