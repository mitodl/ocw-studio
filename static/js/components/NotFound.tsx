import React from "react"

interface Props {
  children?: React.ReactNode
}

/**
 * Our 404 component.
 */
export default function NotFound(props: Props): JSX.Element {
  const { children } = props

  return (
    <div className="w-50 m-auto pt-5">
      <h1>That's a 404!</h1>
      {children}
    </div>
  )
}
