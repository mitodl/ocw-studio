import React from "react"

export default function HomePage(): JSX.Element | null {
  return (
    <div className="container home-page">
      <div className="row pt-5 home-page-div">
        <div className="home-page-background">
          {!SETTINGS.user ? (
            <div className="text-center">
              <a
                href="/login/saml/?idp=default"
                className="btn cyan-button login"
              >
                Login with MIT Touchstone
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
          <a href="https://www.youtube.com/mitocw">
            the MIT OCW channel on YouTube.
          </a>
        </div>
      </div>
    </div>
  )
}
