import React, { SyntheticEvent, useCallback, useEffect, useState } from "react"
import Nestable, { Item } from "react-nestable"
import * as R from "ramda"
import BasicModal from "../BasicModal"
import MenuItemForm, { MenuItemFormValues } from "../forms/MenuItemForm"
import Dialog from "../Dialog"
import { EXTERNAL_LINK_PREFIX } from "../../constants"
import { generateHashCode, isExternalLinkId } from "../../lib/util"

import { LinkType, WebsiteContent } from "../../types/websites"
import { ModalState, createModalState } from "../../types/modal_state"

interface IMenuModalState {
  item: InternalSortableMenuItem
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

export type InternalSortableMenuItem = {
  id: any
  text: string
  targetContentId: string | null
  targetUrl: string | null
  children?: InternalSortableMenuItem[]
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

const hugoItemToInternal = (item: HugoItem): InternalSortableMenuItem => {
  const partialHugoItem: {
    targetContentId: string | null
    targetUrl: string | null
  } = {
    targetContentId: null,
    targetUrl:       null
  }
  if (isExternalLinkId(item.identifier) && item.url) {
    partialHugoItem.targetUrl = item.url
  } else {
    partialHugoItem.targetContentId = item.identifier
  }
  return {
    id:       item.identifier,
    text:     item.name,
    children: [],
    ...partialHugoItem
  }
}

const internalItemToHugo = (
  item: InternalSortableMenuItem,
  siblingIdx: number,
  parent: string | null
): HugoItem => {
  return {
    identifier: item.id,
    name:       item.text,
    weight:     (siblingIdx + 1) * 10,
    ...(item.targetUrl ? { url: item.targetUrl } : {}),
    ...(parent ? { parent: parent } : {})
  }
}

/**
 * Converts from internal representation of the menu items to Hugo-compatible format.
 *
 * EXAMPLE
 *
 * internalItems (internal representation):
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
const internalItemsToHugo = (internalItems: InternalSortableMenuItem[]) => {
  let results = internalItems.map((internalItem, itemIdx) =>
    internalItemToHugo(internalItem, itemIdx, null)
  )
  let itemsToVisit = [...internalItems]
  let parentId: string | null = null
  while (itemsToVisit.length > 0) {
    for (let i = 0; i < itemsToVisit.length; i++) {
      const item = itemsToVisit[0]
      if (item.children && item.children.length > 0) {
        parentId = item.id
        results = results.concat(
          item.children.map((internalItem, itemIdx) =>
            internalItemToHugo(internalItem, itemIdx, parentId)
          )
        )
        itemsToVisit = itemsToVisit.concat(item.children)
      }
      itemsToVisit = itemsToVisit.slice(1)
    }
  }
  return results
}

/**
 * Converts from Hugo-compatible formatted menu items to internal representation. Reverses the example conversion
 * shown in the internalItemsToHugo documentation.
 */
const hugoItemsToInternal = (
  hugoItems: HugoItem[]
): InternalSortableMenuItem[] => {
  if (hugoItems.length === 0) {
    return []
  }
  const parentChildMap: Record<string, HugoItem[]> = {}
  hugoItems.forEach(hugoItem => {
    const key = hugoItem.parent || topLevelKey
    parentChildMap[key] = parentChildMap[key] || []
    parentChildMap[key].push(hugoItem)
  })
  let results: InternalSortableMenuItem[] = parentChildMap[topLevelKey]
    .sort(compareHugoValues)
    .map(hugoItemToInternal)
  const idToResultPath: Record<string, any[]> = Object.fromEntries(
    results.map((result, i) => [result.id, [i]])
  )
  let tierIds = parentChildMap[topLevelKey].map(item => item.identifier)

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
          sortedChildItems.map(hugoItemToInternal),
          results
        )
        sortedChildItems.forEach((childItem, childItemIdx) => {
          idToResultPath[childItem.identifier] = [
            ...childItemPath,
            childItemIdx
          ]
        })
        tierIds = tierIds.concat(childItems.map(item => item.identifier))
      }
      tierIds = tierIds.slice(1)
    }
  }
  return results
}

type ItemPath = Array<string | number>

const getItemPath = (
  items: InternalSortableMenuItem[],
  itemIdToFind: string
): ItemPath => {
  let itemsToSearch: InternalSortableMenuItem[][] = [[...items]]
  const parentPaths: Array<string | number>[] = [[]]
  while (itemsToSearch.length > 0) {
    const parentPath = parentPaths.pop() as Array<string | number>
    const items = itemsToSearch.pop() as InternalSortableMenuItem[]
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
    internalItems: InternalSortableMenuItem[]
  }>(() => {
    const hugoItems = value || []
    return {
      hugoItems:     hugoItems,
      internalItems: hugoItemsToInternal(hugoItems)
    }
  })

  useEffect(() => {
    const hugoItems = value || []
    setMenuData({
      hugoItems:     hugoItems,
      internalItems: hugoItemsToInternal(hugoItems)
    })
  }, [value])

  const [modalState, setModalState] = useState<MenuModalState>(
    createModalState("closed")
  )

  const closeContentModal = useCallback(() => {
    setModalState(createModalState("closed"))
  }, [setModalState])

  const openNewContentPanel = useCallback(
    (e: SyntheticEvent<HTMLButtonElement>) => {
      e.preventDefault()
      setModalState(createModalState("adding"))
    },
    [setModalState]
  )

  const [
    itemToRemove,
    setItemToRemove
  ] = useState<InternalSortableMenuItem | null>(null)

  const closeRemoveDialog = useCallback(() => {
    setItemToRemove(null)
  }, [setItemToRemove])

  const updateValues = (menuItems: InternalSortableMenuItem[]) => {
    const hugoItems = internalItemsToHugo(menuItems)
    setMenuData({
      internalItems: menuItems,
      hugoItems:     hugoItems
    })
    // @ts-ignore
    onChange({ target: { value: hugoItems, name } })
  }

  const startEditMenuItem = (menuItem: InternalSortableMenuItem) => {
    setModalState(
      createModalState("editing", {
        path: getItemPath(menuData.internalItems, menuItem.id),
        item: menuItem
      })
    )
  }

  const removeMenuItem = () => {
    const itemPath = getItemPath(menuData.internalItems, itemToRemove?.id)
    const updatedItems: InternalSortableMenuItem[] = R.dissocPath(
      itemPath,
      menuData.internalItems
    )
    updateValues(updatedItems)
  }

  const onListChange = ({ items }: onChangeProps) => {
    updateValues(items as InternalSortableMenuItem[])
  }

  const renderItem = ({ item }: renderItemProps) => (
    <div className="sortable-item p-2 d-inline-flex w-100">
      <i className="material-icons mr-3 flex-grow-0 reorder">reorder</i>
      <span className="flex-grow-1 menu-title">{item.text}</span>
      <span className="flex-grow-0 d-inline-flex">
        <button
          className="material-icons mr-2 item-action-button"
          onClick={event => {
            event.preventDefault()
            startEditMenuItem(item as InternalSortableMenuItem)
          }}
        >
          settings
        </button>
        <button
          className="material-icons item-action-button"
          onClick={event => {
            event.preventDefault()
            setItemToRemove(item as InternalSortableMenuItem)
          }}
        >
          delete
        </button>
      </span>
    </div>
  )

  // @ts-ignore
  const onSubmitMenuItem = ({
    values,
    hideModal
  }: {
    values: MenuItemFormValues
    hideModal: () => void
  }) => {
    let updatedItems: InternalSortableMenuItem[]
    const updatedItem = {
      text: values.menuItemTitle,
      ...(values.menuItemType === LinkType.External ?
        {
          id: `${EXTERNAL_LINK_PREFIX}${generateHashCode(
            values.externalLink
          )}-${Date.now().toString()}`,
          targetUrl:       values.externalLink,
          targetContentId: null
        } :
        {
          id:              values.internalLink,
          targetUrl:       null,
          targetContentId: values.internalLink
        })
    }
    if (modalState.editing()) {
      const activeItemLens = R.lensPath(modalState.wrapped.path)
      const currentItem = R.view(activeItemLens, menuData.internalItems)
      updatedItems = R.set(
        activeItemLens,
        {
          ...currentItem,
          ...updatedItem
        },
        menuData.internalItems
      )
    } else {
      updatedItems = [
        ...menuData.internalItems,
        {
          ...updatedItem,
          children: []
        }
      ]
    }
    updateValues(updatedItems)
    hideModal()
  }

  const existingMenuIds = new Set(
    menuData.hugoItems.map(hugoItem => hugoItem.identifier)
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
        {modalProps => (
          <div className="m-3">
            <MenuItemForm
              activeItem={modalState.editing() ? modalState.wrapped.item : null}
              existingMenuIds={existingMenuIds}
              onSubmit={values => {
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
          items={menuData.internalItems}
          renderItem={renderItem}
          onChange={onListChange}
        />
      </div>
    </>
  )
}
