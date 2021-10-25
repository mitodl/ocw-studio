import React from "react"

export default function Footer(): JSX.Element {
  return (
    <footer>
      <div className="p-4">
        <div className="float-left">
          &copy;2021 Massachusetts Institute of Technology
        </div>
        <div className="float-right">
          <a href="/privacy-policy">Privacy Policy</a>
        </div>
      </div>
    </footer>
  )
}
