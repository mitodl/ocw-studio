import React from "react"
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
} from "@dnd-kit/core"
import {
  SortableContext,
  SortingStrategy,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable"

interface Props<T> {
  children: React.ReactNode
  handleDragEnd: (event: DragEndEvent) => void
  items: T[]
  generateItemUUID: (item: T) => string
  /** How items rearrange while dragging; a vertical list by default. */
  strategy?: SortingStrategy
}

export default function Sortable<T>(props: Props<T>): JSX.Element {
  const {
    children,
    handleDragEnd,
    items,
    generateItemUUID,
    strategy = verticalListSortingStrategy,
  } = props

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    }),
  )

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragEnd={handleDragEnd}
    >
      <SortableContext items={items.map(generateItemUUID)} strategy={strategy}>
        {children}
      </SortableContext>
    </DndContext>
  )
}
