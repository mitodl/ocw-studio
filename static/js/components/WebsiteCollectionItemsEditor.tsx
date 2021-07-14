import React, { useCallback } from "react"
import { useSelector } from "react-redux"
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors
} from "@dnd-kit/core"
import {
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy
} from "@dnd-kit/sortable"

import { useMutation, useRequest } from "redux-query-react"
import { WebsiteCollection } from "../types/website_collections"
import {
  editWebsiteCollectionItemMutation,
  websiteCollectionItemsRequest
} from "../query-configs/website_collections"
import { getWebsiteCollectionItemsCursor } from "../selectors/website_collections"
import WebsiteCollectionItemForm from "./forms/WebsiteCollectionItemForm"
import SortableWebsiteCollectionItem from "./SortableWebsiteCollectionItem"

interface Props {
  websiteCollection: WebsiteCollection
}

export default function WebsiteCollectionItemsEditor(
  props: Props
): JSX.Element {
  const { websiteCollection } = props

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates
    })
  )

  useRequest(websiteCollectionItemsRequest(websiteCollection.id))

  const websiteCollectionItemsCursor = useSelector(
    getWebsiteCollectionItemsCursor
  )

  const items = websiteCollectionItemsCursor(websiteCollection.id)

  const [, updateWCItemPosition] = useMutation(
    editWebsiteCollectionItemMutation
  )

  const handleDragEnd = useCallback(
    function handleDragEnd(event: any) {
      const { active, over } = event

      if (active.id !== over.id) {
        updateWCItemPosition(
          {
            position: items.map(item => String(item.id)).indexOf(over.id)
          },
          websiteCollection.id,
          active.id
        )
      }
    },
    [updateWCItemPosition, websiteCollection, items]
  )

  return (
    <div className="collection-item-editor pt-5 pb-3">
      <h4>Courses in this collection</h4>
      <WebsiteCollectionItemForm websiteCollection={websiteCollection} />
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={handleDragEnd}
      >
        <SortableContext
          items={items.map(item => String(item.id))}
          strategy={verticalListSortingStrategy}
        >
          {items.map(item => (
            <SortableWebsiteCollectionItem
              key={item.id}
              id={String(item.id)}
              item={item}
            />
          ))}
        </SortableContext>
      </DndContext>
    </div>
  )
}
