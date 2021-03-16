import * as React from "react"
import { NavLink } from "react-router-dom"

import { siteCollaboratorsUrl, siteContentListingUrl } from "../lib/urls"

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
          <NavLink
            exact
            to={siteContentListingUrl
              .param({ name: website.name, contentType: item.name })
              .toString()}
          >
            {item.label}
          </NavLink>
        </li>
      ))}
      {website.is_admin ? (
        <li>
          Settings
          <ul>
            <NavLink
              exact
              to={siteCollaboratorsUrl.param({ name: website.name }).toString()}
            >
              Collaborators
            </NavLink>
          </ul>
        </li>
      ) : null}
    </ul>
  )
}
