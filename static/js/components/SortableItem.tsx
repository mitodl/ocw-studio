import React, { useCallback } from "react"
import { useSortable } from "@dnd-kit/sortable"
import { CSS } from "@dnd-kit/utilities"

interface Props<T> {
  item: T
  id: string
  deleteItem: (item: T) => void
  title: string
}

export default function SortableItem<T>(props: Props<T>): JSX.Element {
  const { item, deleteItem, id, title } = props

  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition
  } = useSortable({
    id
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
      <div className="title">{title}</div>
      <span
        className="material-icons ml-auto gray-button hover"
        onClick={deleteItemCB}
      >
        remove_circle_outline
      </span>
    </div>
  )
}
