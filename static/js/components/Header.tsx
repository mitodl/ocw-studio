import * as React from "react"
import { useCallback, useState } from "react"
import { Link } from "react-router-dom"

import PublishDrawer from "../components/PublishDrawer"

import { logoutUrl, sitesBaseUrl } from "../lib/urls"

import { Website } from "../types/websites"

export interface HeaderProps {
  website?: Website | null
}

export default function Header(props: HeaderProps): JSX.Element {
  const { website } = props

  const [drawerOpen, setDrawerOpen] = useState<boolean>(false)
  const openPublishDrawer = useCallback(
    (event: any) => {
      event.preventDefault()
      setDrawerOpen(true)
    },
    [setDrawerOpen]
  )

  return (
    <header className="p-3">
      <div className="d-flex justify-content-between">
        <div>
          <Link to={sitesBaseUrl.toString()}>
            <img
              className="logo"
              src="/static/images/ocw-studio-logo.png"
              alt="OCW Studio"
            />
          </Link>
        </div>
        {SETTINGS.user !== null ? (
          <div className="links">
            <span className="pr-5">{SETTINGS.user.name}</span>
            <a href={logoutUrl.toString()}>Log out</a>
          </div>
        ) : null}
      </div>
      {website && (
        <div className="d-flex justify-content-between mt-3 site-header">
          <h2 className="my-0 mr-1 p-0">{website.title}</h2>
          <div className="flex-shrink-0">
            <button
              type="button"
              onClick={openPublishDrawer}
              className="btn cyan-button-outline"
            >
              <i className="material-icons mr-1">publish</i> Publish
            </button>
            <PublishDrawer
              website={website}
              visibility={drawerOpen}
              toggleVisibility={() => setDrawerOpen(visibility => !visibility)}
            />
          </div>
        </div>
      )}
    </header>
  )
}
