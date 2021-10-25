import React from "react"

export default function HomePage(): JSX.Element | null {
  return (
    <div className="container home-page">
      <div className="row pt-5 home-page-div">
        <div className="d-flex align-items-center justify-content-center home-page-logo">
          <img src="/static/images/mit-logo.png" className="pr-2" />
          <img src="/static/images/ocw-white-logo.png" className="pl-2" />
        </div>
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
        OCW Studio is a content management tool for creating the MIT
        OpenCourseWare site. Users can create pages and upload static files and
        videos from Google drive. Videos are published to YouTube.
      </div>
    </div>
  )
}
