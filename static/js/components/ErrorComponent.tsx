import React from "react"

interface Props {
  children?: React.ReactNode
}

export default function ErrorComponent(props: Props): JSX.Element {
  const { children } = props

  return <div className="w-50 m-auto pt-5">{children}</div>
}
