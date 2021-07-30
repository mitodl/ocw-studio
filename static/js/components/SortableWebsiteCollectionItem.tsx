import React, { useCallback } from "react"
import { useSortable } from "@dnd-kit/sortable"
import { CSS } from "@dnd-kit/utilities"

import { WebsiteCollectionItem } from "../types/website_collections"

interface Props {
  item: WebsiteCollectionItem
  id: string
  deleteItem: (item: WebsiteCollectionItem) => void
}

export default function SortableWebsiteCollectionItem(
  props: Props
): JSX.Element {
  const { item, deleteItem } = props

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

  const deleteItemCB = useCallback(() => {
    deleteItem(item)
  }, [deleteItem, item])

  return (
    <div
      className="d-flex my-3"
      ref={setNodeRef}
      // @ts-ignore unfortunately unavoidable because of library types :/
      style={style}
      {...attributes}
      {...listeners}
    >
      <span className="material-icons">drag_indicator</span>
      <div className="title">{item.website_title}</div>
      <span
        className="material-icons ml-auto gray-button hover"
        onClick={deleteItemCB}
      >
        remove_circle_outline
      </span>
    </div>
  )
}
