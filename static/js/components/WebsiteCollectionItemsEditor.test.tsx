import WebsiteCollectionItemsEditor from "./WebsiteCollectionItemsEditor"
import { times } from "lodash"
import { DndContext } from "@dnd-kit/core"

import IntegrationTestHelper, {
  TestRenderer
} from "../util/integration_test_helper"
import {
  WebsiteCollection,
  WebsiteCollectionItem
} from "../types/website_collections"
import {
  makeWebsiteCollection,
  makeWebsiteCollectionItem
} from "../util/factories/website_collections"
import { wcItemsApiDetailUrl, wcItemsApiUrl } from "../lib/urls"
import { act } from "react-dom/test-utils"

describe("WebsiteCollectionItemsEditor", () => {
  let helper: IntegrationTestHelper,
    render: TestRenderer,
    collection: WebsiteCollection,
    items: WebsiteCollectionItem[]

  beforeEach(() => {
    collection = makeWebsiteCollection()
    items = times(15).map(() => makeWebsiteCollectionItem(collection))
    helper = new IntegrationTestHelper()
    render = helper.configureRenderer(WebsiteCollectionItemsEditor, {
      websiteCollection: collection
    })

    helper.handleRequestStub
      .withArgs(wcItemsApiUrl.param({ collectionId: collection.id }).toString())
      .returns({
        body:   items,
        status: 200
      })
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("should render, show items", async () => {
    const { wrapper } = await render()
    expect(wrapper.find("SortableItem").map(item => item.prop("item"))).toEqual(
      items
    )
  })

  it("should render the WebsiteCollectionItemForm", async () => {
    const { wrapper } = await render()
    expect(wrapper.find("WebsiteCollectionItemForm").exists()).toBeTruthy()
    expect(
      wrapper.find("WebsiteCollectionItemForm").prop("websiteCollection")
    ).toBe(collection)
  })

  it("should have a SortableContext with items", async () => {
    const { wrapper } = await render()
    const context = wrapper.find("SortableContext")
    expect(context.exists()).toBeTruthy()
    expect(context.prop("items")).toEqual(items.map(item => String(item.id)))
  })

  it("should issue properly-formed requests to reordering items", async () => {
    const { wrapper } = await render()

    const itemToMove = items[6]

    helper.handleRequestStub
      .withArgs(
        wcItemsApiDetailUrl
          .param({ collectionId: collection.id, itemId: items[6].id })
          .toString()
      )
      .returns({
        status: 200,
        body:   {
          id: items[6].id
        }
      })

    act(() => {
      wrapper.find(DndContext)!.prop("onDragEnd")!({
        active: { id: String(itemToMove.id) },
        over:   { id: String(items[2].id) }
      } as any)
    })
    expect(helper.handleRequestStub.args[1]).toEqual([
      wcItemsApiDetailUrl
        .param({ collectionId: collection.id, itemId: items[6].id })
        .toString(),
      "PATCH",
      {
        body: {
          position: 2
        },
        credentials: undefined,
        headers:     {
          "X-CSRFTOKEN": ""
        }
      }
    ])
  })

  it("should pass down a delete callback to sortable items", async () => {
    const { wrapper } = await render()
    const [item] = items

    helper.handleRequestStub
      .withArgs(
        wcItemsApiDetailUrl
          .param({ collectionId: collection.id, itemId: item.id })
          .toString()
      )
      .returns({
        status: 204
      })

    act(() => {
      // @ts-ignore
      wrapper
        .find("SortableItem")
        .at(0)
        .prop("deleteItem")(item)
    })

    expect(helper.handleRequestStub.args[1]).toEqual([
      wcItemsApiDetailUrl
        .param({ collectionId: collection.id, itemId: item.id })
        .toString(),
      "DELETE",
      {
        credentials: undefined,
        headers:     {
          "X-CSRFTOKEN": ""
        }
      }
    ])
  })
})
