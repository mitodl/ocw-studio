import React from "react"

interface Props {
  children: React.ReactNode
}

export default function Card(props: Props): JSX.Element {
  const { children } = props

  return (
    <div className="studio-card h-100">
      <div className="card-contents p-4">{children}</div>
    </div>
  )
}
