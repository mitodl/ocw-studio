import React, { SyntheticEvent, useCallback, useEffect, useState } from "react"
import Nestable, { Item } from "react-nestable"
import * as R from "ramda"
import BasicModal from "../BasicModal"
import MenuItemForm, { MenuItemFormValues } from "../forms/MenuItemForm"
import Dialog from "../Dialog"

import { WebsiteContent } from "../../types/websites"
import { ModalState, createModalState } from "../../types/modal_state"

interface IMenuModalState {
  item: SortableMenuItem
  path: ItemPath
}

type MenuModalState = ModalState<IMenuModalState>

interface MenuFieldProps {
  name: string
  value: HugoItem[]
  onChange: (event: Event) => void
  collections?: string[]
  contentContext: WebsiteContent[] | null
}

export type HugoItem = {
  identifier: string
  name: string
  url?: string
  weight: number
  parent?: string
}

export type SortableMenuItem = {
  id: any
  text: string
  targetContentId: string | null
  targetUrl: string | null
  children?: SortableMenuItem[]
}

type onChangeProps = {
  items: Item[]
  dragItem: Item
  targetPath: number[]
}

type renderItemProps = {
  collapseIcon: React.ReactNode
  depth: number
  handler: React.ReactNode
  index: number
  item: Item
}

const topLevelKey = "_"

const compareHugoValues = (item1: HugoItem, item2: HugoItem): number =>
  item1.weight < item2.weight ? -1 : 1

const hugoItemToContent = (item: HugoItem): SortableMenuItem => {
  const partialHugoItem: {
    targetContentId: string | null
    targetUrl: string | null
  } = {
    targetContentId: null,
    targetUrl: null,
  }

  partialHugoItem.targetContentId = item.identifier

  return {
    id: item.identifier,
    text: item.name,
    children: [],
    ...partialHugoItem,
  }
}

const contentItemToHugo = (
  item: SortableMenuItem,
  siblingIdx: number,
  parent: string | null,
): HugoItem => {
  return {
    identifier: item.id,
    name: item.text,
    weight: (siblingIdx + 1) * 10,
    ...(item.targetUrl ? { url: item.targetUrl } : {}),
    ...(parent ? { parent: parent } : {}),
  }
}

/**
 * Converts from content representation of the menu items to Hugo-compatible format.
 *
 * EXAMPLE
 *
 * contentItems (content representation):
    [
      {
        "id": "d4d624af-f5ac-4de6-a8de-472ce2394ed9",
        "text": "Page 1",
        "children": [
          {
            "id": "fab78dfb-e978-40a7-a6c7-ab7a3b663d86",
            "text": "Page 2",
            "children": [],
            "targetContentId": "fab78dfb-e978-40a7-a6c7-ab7a3b663d86",
            "targetUrl": null
          }
        ],
        "targetContentId": "d4d624af-f5ac-4de6-a8de-472ce2394ed9",
        "targetUrl": null
      },
      {
        "id": "-631280213-1625602835034",
        "text": "ext link 1",
        "children": [],
        "targetContentId": null,
        "targetUrl": "http://example.com"
      }
    ]

  * Return value:
    [
      {
        "name": "Page 1",
        "weight": 0,
        "identifier": "d4d624af-f5ac-4de6-a8de-472ce2394ed9"
      },
      {
        "url": "http://example.com",
        "name": "ext link 1",
        "weight": 10,
        "identifier": "-631280213-1625602835034"
      },
      {
        "name": "Page 2",
        "parent": "d4d624af-f5ac-4de6-a8de-472ce2394ed9",
        "weight": 0,
        "identifier": "fab78dfb-e978-40a7-a6c7-ab7a3b663d86"
      }
    ]
 */
const contentItemsToHugo = (contentItems: SortableMenuItem[]) => {
  let results = contentItems.map((contentItem, itemIdx) =>
    contentItemToHugo(contentItem, itemIdx, null),
  )
  let itemsToVisit = [...contentItems]
  let parentId: string | null = null
  while (itemsToVisit.length > 0) {
    for (let i = 0; i < itemsToVisit.length; i++) {
      const item = itemsToVisit[0]
      if (item.children && item.children.length > 0) {
        parentId = item.id
        results = results.concat(
          item.children.map((contentItem, itemIdx) =>
            contentItemToHugo(contentItem, itemIdx, parentId),
          ),
        )
        itemsToVisit = itemsToVisit.concat(item.children)
      }
      itemsToVisit = itemsToVisit.slice(1)
    }
  }
  return results
}

/**
 * Converts from Hugo-compatible formatted menu items to content representation. Reverses the example conversion
 * shown in the contentItemsToHugo documentation.
 */
const hugoItemsToContent = (hugoItems: HugoItem[]): SortableMenuItem[] => {
  if (hugoItems.length === 0) {
    return []
  }
  const parentChildMap: Record<string, HugoItem[]> = {}
  hugoItems.forEach((hugoItem) => {
    const key = hugoItem.parent || topLevelKey
    parentChildMap[key] = parentChildMap[key] || []
    parentChildMap[key].push(hugoItem)
  })
  let results: SortableMenuItem[] = parentChildMap[topLevelKey]
    .sort(compareHugoValues)
    .map(hugoItemToContent)
  const idToResultPath: Record<string, any[]> = Object.fromEntries(
    results.map((result, i) => [result.id, [i]]),
  )
  let tierIds = parentChildMap[topLevelKey].map((item) => item.identifier)

  while (tierIds.length > 0) {
    for (let i = 0; i < tierIds.length; i++) {
      const itemId = tierIds[0]
      const itemPath = idToResultPath[itemId]
      const childItems = parentChildMap[itemId]
      if (childItems && childItems.length > 0) {
        const childItemPath = [...itemPath, "children"]
        const sortedChildItems = childItems.sort(compareHugoValues)
        results = R.set(
          R.lensPath(childItemPath),
          sortedChildItems.map(hugoItemToContent),
          results,
        )
        sortedChildItems.forEach((childItem, childItemIdx) => {
          idToResultPath[childItem.identifier] = [
            ...childItemPath,
            childItemIdx,
          ]
        })
        tierIds = tierIds.concat(childItems.map((item) => item.identifier))
      }
      tierIds = tierIds.slice(1)
    }
  }
  return results
}

type ItemPath = Array<string | number>

const getItemPath = (
  items: SortableMenuItem[],
  itemIdToFind: string,
): ItemPath => {
  let itemsToSearch: SortableMenuItem[][] = [[...items]]
  const parentPaths: Array<string | number>[] = [[]]
  while (itemsToSearch.length > 0) {
    const parentPath = parentPaths.pop() as Array<string | number>
    const items = itemsToSearch.pop() as SortableMenuItem[]
    for (let idx = 0; idx < items.length; idx++) {
      const item = items[idx]
      if (item.id === itemIdToFind) {
        return [...parentPath, idx]
      }
      if (item.children && item.children.length) {
        itemsToSearch = itemsToSearch.concat([item.children])
        parentPaths.push([...parentPath, idx, "children"])
      }
    }
  }
  return []
}

export default function MenuField(props: MenuFieldProps): JSX.Element {
  const { name, value, onChange, collections, contentContext } = props

  const [menuData, setMenuData] = useState<{
    hugoItems: HugoItem[]
    contentItems: SortableMenuItem[]
  }>(() => {
    const hugoItems = value || []
    return {
      hugoItems: hugoItems,
      contentItems: hugoItemsToContent(hugoItems),
    }
  })

  useEffect(() => {
    const hugoItems = value || []
    setMenuData({
      hugoItems: hugoItems,
      contentItems: hugoItemsToContent(hugoItems),
    })
  }, [value])

  const [modalState, setModalState] = useState<MenuModalState>(
    createModalState("closed"),
  )

  const closeContentModal = useCallback(() => {
    setModalState(createModalState("closed"))
  }, [setModalState])

  const openNewContentPanel = useCallback(
    (e: SyntheticEvent<HTMLButtonElement>) => {
      e.preventDefault()
      setModalState(createModalState("adding"))
    },
    [setModalState],
  )

  const [itemToRemove, setItemToRemove] = useState<SortableMenuItem | null>(
    null,
  )

  const closeRemoveDialog = useCallback(() => {
    setItemToRemove(null)
  }, [setItemToRemove])

  const updateValues = (menuItems: SortableMenuItem[]) => {
    const hugoItems = contentItemsToHugo(menuItems)
    setMenuData({
      contentItems: menuItems,
      hugoItems: hugoItems,
    })
    // @ts-expect-error the type of onChange is not quite right
    onChange({ target: { value: hugoItems, name } })
  }

  const startEditMenuItem = (menuItem: SortableMenuItem) => {
    setModalState(
      createModalState("editing", {
        path: getItemPath(menuData.contentItems, menuItem.id),
        item: menuItem,
      }),
    )
  }

  const removeMenuItem = () => {
    const itemPath = getItemPath(menuData.contentItems, itemToRemove?.id)
    const updatedItems: SortableMenuItem[] = R.dissocPath(
      itemPath,
      menuData.contentItems,
    )
    updateValues(updatedItems)
  }

  const onListChange = ({ items }: onChangeProps) => {
    updateValues(items as SortableMenuItem[])
  }

  const renderItem = ({ item }: renderItemProps) => (
    <div className="sortable-item p-2 d-inline-flex w-100">
      <i className="material-icons mr-3 flex-grow-0 reorder">reorder</i>
      <span className="flex-grow-1 menu-title">{item.text}</span>
      <span className="flex-grow-0 d-inline-flex">
        <button
          className="material-icons mr-2 item-action-button"
          onClick={(event) => {
            event.preventDefault()
            startEditMenuItem(item as SortableMenuItem)
          }}
        >
          settings
        </button>
        <button
          className="material-icons item-action-button"
          onClick={(event) => {
            event.preventDefault()
            setItemToRemove(item as SortableMenuItem)
          }}
        >
          delete
        </button>
      </span>
    </div>
  )

  const onSubmitMenuItem = ({
    values,
    hideModal,
  }: {
    values: MenuItemFormValues
    hideModal: () => void
  }) => {
    let updatedItems: SortableMenuItem[]
    const updatedItem = {
      text: values.menuItemTitle,
      ...{
        id: values.contentLink,
        targetUrl: null,
        targetContentId: values.contentLink,
      },
    }
    if (modalState.editing()) {
      const activeItemLens = R.lensPath(modalState.wrapped.path)
      const currentItem = R.view(activeItemLens, menuData.contentItems)
      updatedItems = R.set(
        activeItemLens,
        {
          ...currentItem,
          ...updatedItem,
        },
        menuData.contentItems,
      )
    } else {
      updatedItems = [
        ...menuData.contentItems,
        {
          ...updatedItem,
          children: [],
        },
      ]
    }
    updateValues(updatedItems)
    hideModal()
  }

  const existingMenuIds = new Set(
    menuData.hugoItems.map((hugoItem) => hugoItem.identifier),
  )

  return (
    <>
      <BasicModal
        isVisible={modalState.open()}
        hideModal={closeContentModal}
        title={
          modalState.adding() ? "Add Navigation Item" : "Edit Navigation Item"
        }
        className="right"
      >
        {(modalProps) => (
          <div className="m-3">
            <MenuItemForm
              activeItem={modalState.editing() ? modalState.wrapped.item : null}
              existingMenuIds={existingMenuIds}
              onSubmit={(values) => {
                onSubmitMenuItem({ values, hideModal: modalProps.hideModal })
              }}
              contentContext={contentContext}
              {...(collections ? { collections: collections } : {})}
            />
          </div>
        )}
      </BasicModal>
      <Dialog
        open={!!itemToRemove}
        onCancel={closeRemoveDialog}
        headerContent={"Remove collaborator"}
        bodyContent={`Are you sure you want to remove "${itemToRemove?.text}"`}
        acceptText="Remove"
        onAccept={() => {
          removeMenuItem()
          closeRemoveDialog()
        }}
      />
      <div>
        <div className="form-group w-100">
          <button
            className="px-3 btn cyan-button"
            onClick={openNewContentPanel}
          >
            Add New
          </button>
        </div>
        <Nestable
          items={menuData.contentItems}
          renderItem={renderItem}
          onChange={onListChange}
        />
      </div>
    </>
  )
}
