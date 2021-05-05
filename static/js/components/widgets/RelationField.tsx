import React from "react"

interface Props {
  collection: string
  display_field: string
  max: number
  min: number
  multiple: boolean
  search_fields: string[]
}

export default function RelationField(props: Props): JSX.Element {
  const { collection, display_field, max, min, multiple, search_fields } = props

  return <div>hey!</div>
}
