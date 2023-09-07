import React, { useCallback } from "react"
import { useAppDispatch, useAppSelector } from "../hooks/redux"
import { Link } from "react-router-dom"
import { requestAsync } from "redux-query"
import useInterval from "@use-it/interval"

import { useSearchParams } from "../hooks/search"

import PublishDrawer from "../components/PublishDrawer"

import { logoutUrl, sitesBaseUrl } from "../lib/urls"
import { websiteStatusRequest } from "../query-configs/websites"
import { PUBLISH_STATUS_PROCESSING_STATES } from "../constants"
import PublishStatusIndicator from "./PublishStatusIndicator"

import { Website } from "../types/websites"
import { latestPublishStatus } from "../lib/website"

export interface HeaderProps {
  website?: Website | null
}

export default function Header(props: HeaderProps): JSX.Element {
  const { website } = props
  const dispatch = useAppDispatch()
  const { user } = useAppSelector((state) => state.user)
  const [search, setSearchParams] = useSearchParams()
  const drawerOpen = search.has("publish")

  const openPublishDrawer = useCallback(() => {
    const newParams = new URLSearchParams(search)
    newParams.set("publish", "")
    setSearchParams(newParams)
  }, [search, setSearchParams])
  const closePublishDrawer = useCallback(() => {
    const newParams = new URLSearchParams(search)
    newParams.delete("publish")
    setSearchParams(newParams)
  }, [search, setSearchParams])

  useInterval(
    async () => {
      if (
        website &&
        ((website.draft_publish_status &&
          PUBLISH_STATUS_PROCESSING_STATES.includes(
            website.draft_publish_status,
          )) ||
          (website.live_publish_status &&
            PUBLISH_STATUS_PROCESSING_STATES.includes(
              website.live_publish_status,
            )))
      ) {
        try {
          await dispatch(requestAsync(websiteStatusRequest(website.name)))
        } catch (err) {
          console.error(err)
        }
      }
    },
    website ? 5000 : null,
  )

  return (
    <header className="p-3">
      <div className="d-flex justify-content-between">
        <div>
          <a href="https://www.mit.edu" target="_blank" rel="noreferrer">
            <img
              src="/static/images/mit-logo.png"
              className="pr-1 border-right border-dark"
              alt="MIT"
            />
          </a>
          <Link to={sitesBaseUrl.toString()}>
            <img
              className="logo pl-2"
              src="/static/images/ocw-studio-logo.png"
              alt="OCW Studio"
            />
          </Link>
        </div>
        {user !== null ? (
          <div className="links">
            <span className="pr-5">{user.name}</span>
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
              title="Publish"
            >
              <i className="material-icons mr-1">publish</i> Publish
            </button>
            <PublishStatusIndicator status={latestPublishStatus(website)} />
            <PublishDrawer
              website={website}
              visibility={drawerOpen}
              toggleVisibility={closePublishDrawer}
            />
          </div>
        </div>
      )}
    </header>
  )
}
