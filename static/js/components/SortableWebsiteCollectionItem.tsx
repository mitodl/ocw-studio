import React from "react"
import { useSortable } from "@dnd-kit/sortable"
import { CSS } from "@dnd-kit/utilities"

import { WebsiteCollectionItem } from "../types/website_collections"

interface Props {
  item: WebsiteCollectionItem
  id: string
}

export default function SortableWebsiteCollectionItem(
  props: Props
): JSX.Element {
  const { item } = props
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition
  } = useSortable({
    id: String(item.id)
  })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition
  }

  return (
    <div
      className="d-flex my-3"
      ref={setNodeRef}
      // @ts-ignore
      style={style}
      {...attributes}
      {...listeners}
    >
      <span className="material-icons">drag_indicator</span>
      <div className="title">{item.website_title}</div>
    </div>
  )
}
