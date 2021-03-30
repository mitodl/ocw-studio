import * as React from "react"

export default function Header(): JSX.Element {
  return (
    <header className="p-3 m-3 d-flex">
      <h2 className="p-0 m-0 pl-2">OCW Studio</h2>

      {SETTINGS.user !== null ? (
        <>
          <span className="ml-auto p-1 pr-3">{SETTINGS.user.name}</span>
          <a href="/logout" className="btn blue-button">
            Logout
          </a>
        </>
      ) : null}
    </header>
  )
}
