import React from "react"

export default function HomePage(): JSX.Element | null {
  return (
    <div className="d-flex align-items-center justify-content-center home-page">
      {!SETTINGS.user ? (
        <a href="/login/saml/?idp=default" className="btn green-button">
          Login with MIT Touchstone
        </a>
      ) : null}
    </div>
  )
}
