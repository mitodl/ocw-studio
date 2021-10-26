import * as React from "react"
import { useCallback, useState } from "react"
import { useStore } from "react-redux"
import { Link } from "react-router-dom"
import { requestAsync } from "redux-query"
import useInterval from "@use-it/interval"

import PublishDrawer from "../components/PublishDrawer"

import { logoutUrl, sitesBaseUrl } from "../lib/urls"
import { websiteStatusRequest } from "../query-configs/websites"
import { PUBLISH_STATUS_PROCESSING_STATES } from "../constants"
import PublishStatusIndicator from "./PublishStatusIndicator"

import { Website } from "../types/websites"

export interface HeaderProps {
  website?: Website | null
}

export default function Header(props: HeaderProps): JSX.Element {
  const { website } = props
  const store = useStore()

  const [drawerOpen, setDrawerOpen] = useState<boolean>(false)
  const openPublishDrawer = useCallback(
    (event: any) => {
      event.preventDefault()
      setDrawerOpen(true)
    },
    [setDrawerOpen]
  )

  useInterval(
    async () => {
      if (
        website &&
        ((website.draft_publish_status &&
          PUBLISH_STATUS_PROCESSING_STATES.includes(
            website.draft_publish_status
          )) ||
          (website.live_publish_status &&
            PUBLISH_STATUS_PROCESSING_STATES.includes(
              website.live_publish_status
            )))
      ) {
        await store.dispatch(requestAsync(websiteStatusRequest(website.name)))
      }
    },
    website ? 5000 : null
  )

  const latestPublishStatus = website ?
    (website.draft_publish_status_updated_on ?? "") <
      (website.live_publish_status_updated_on ?? "") ?
      website.live_publish_status :
      website.draft_publish_status :
    null

  return (
    <header className="p-3">
      <div className="d-flex justify-content-between">
        <div>
          <Link to="https://www.mit.edu">
            <img
              src="/static/images/mit-logo.png"
              className="pr-1 border-right border-dark"
            />
          </Link>
          <Link to={sitesBaseUrl.toString()}>
            <img
              className="logo pl-2"
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
            <PublishStatusIndicator status={latestPublishStatus} />
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
