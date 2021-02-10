import * as React from "react"
import { NavLink } from "react-router-dom"

import { siteComponentUrl, siteUrl } from "../lib/urls"

import { ConfigItem, Website } from "../types/websites"

interface Props {
  website: Website
}
export default function SiteSidebar(props: Props): JSX.Element {
  const { website } = props

  const configItems: ConfigItem[] = website.starter?.config?.collections ?? []

  return (
    <div className="sidebar">
      <ul>
        <li>
          <NavLink exact to={siteUrl(website.name)} activeClassName={"active"}>
            Content
          </NavLink>
          <ul>
            {configItems.map(item => (
              <li key={item.name}>
                <NavLink exact to={siteComponentUrl(website.name, item.name)}>
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </li>
        <li>
          Settings
          <ul>
            <li>Collaborators</li>
          </ul>
        </li>
      </ul>
    </div>
  )
}
