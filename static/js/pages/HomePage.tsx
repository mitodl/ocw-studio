import React from "react"
import { useAppSelector } from "../hooks/redux"
import { postTo } from "../lib/navigation"
import DocumentTitle, { formatTitle } from "../components/DocumentTitle"

export default function HomePage(): JSX.Element | null {
  const { user } = useAppSelector((state) => state.user)
  return (
    <div className="container home-page">
      <DocumentTitle title={formatTitle()} />
      <div className="row pt-5 home-page-div">
        <div className="home-page-background">
          {!user ? (
            <div className="text-center">
              <a
                href="/auth/login/keycloak/"
                className="btn cyan-button login"
                onClick={(e) => {
                  e.preventDefault()
                  postTo("/auth/login/keycloak/")
                }}
              >
                Login with MIT Keycloak
              </a>
            </div>
          ) : null}
        </div>
      </div>
      <div className="row pt-3 pb-3">
        <div className="col description">
          OCW Studio integrates with Google Drive and YouTube via their
          respective APIs. The app can import static files saved in a MIT shared
          Google Drive and also publishes videos to{" "}
          <a href="https://www.youtube.com/mitocw" className="underline">
            the MIT OCW channel on YouTube.
          </a>
        </div>
      </div>
    </div>
  )
}
