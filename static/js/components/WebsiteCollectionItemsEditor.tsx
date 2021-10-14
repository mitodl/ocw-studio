import React, { useCallback } from "react"
import { useSelector } from "react-redux"

import { useMutation, useRequest } from "redux-query-react"
import {
  WebsiteCollection,
  WebsiteCollectionItem
} from "../types/website_collections"
import {
  deleteWebsiteCollectionItemMutation,
  editWebsiteCollectionItemMutation,
  websiteCollectionItemsRequest
} from "../query-configs/website_collections"
import { getWebsiteCollectionItemsCursor } from "../selectors/website_collections"
import WebsiteCollectionItemForm from "./forms/WebsiteCollectionItemForm"
import SortableItem from "./SortableItem"
import SortWrapper from "./SortWrapper"
import { DragEndEvent } from "@dnd-kit/core"

interface Props {
  websiteCollection: WebsiteCollection
}

export default function WebsiteCollectionItemsEditor(
  props: Props
): JSX.Element {
  const { websiteCollection } = props

  useRequest(websiteCollectionItemsRequest(websiteCollection.id))

  const websiteCollectionItemsCursor = useSelector(
    getWebsiteCollectionItemsCursor
  )

  const items = websiteCollectionItemsCursor(websiteCollection.id)

  const [, updateWCItemPosition] = useMutation(
    editWebsiteCollectionItemMutation
  )

  const handleDragEnd = useCallback(
    function handleDragEnd(event: DragEndEvent) {
      const { active, over } = event

      if (over && active.id !== over.id) {
        updateWCItemPosition(
          {
            position: items.map(item => String(item.id)).indexOf(over.id)
          },
          websiteCollection.id,
          Number(active.id)
        )
      }
    },
    [updateWCItemPosition, websiteCollection, items]
  )

  const [, deleteWCItem] = useMutation((item: WebsiteCollectionItem) =>
    deleteWebsiteCollectionItemMutation(item, websiteCollection)
  )

  return (
    <div className="collection-item-editor pt-5 pb-3">
      <h4>Courses in this collection</h4>
      <WebsiteCollectionItemForm websiteCollection={websiteCollection} />
      <SortWrapper
        handleDragEnd={handleDragEnd}
        items={items}
        generateItemUUID={item => String(item.id)}
      >
        {items.map(item => (
          <SortableItem
            key={item.id}
            id={String(item.id)}
            item={item}
            deleteItem={deleteWCItem}
            title={item.website_title}
          />
        ))}
      </SortWrapper>
    </div>
  )
}
