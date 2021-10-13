import React from "react"
import { Link } from "react-router-dom"

interface Props {
  previous: string
  next: string
  listing: any
}

export default function PaginationControls(props: Props): JSX.Element {
  const { previous, next, listing } = props

  return (
    <div className="pagination pt-2 justify-content-center">
      {listing.previous ? (
        <Link to={previous} className="d-flex p-0 btn cyan-button previous">
          <i className="material-icons">keyboard_arrow_left</i>
        </Link>
      ) : null}
      &nbsp;
      {listing.next ? (
        <Link to={next} className="d-flex p-0 btn cyan-button next">
          <i className="material-icons">keyboard_arrow_right</i>
        </Link>
      ) : null}
    </div>
  )
}
