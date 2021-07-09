import WebsiteCollectionsPage from "./WebsiteCollectionsPage"

import IntegrationTestHelper, {
  TestRenderer
} from "../util/integration_test_helper"
import { WebsiteCollection } from "../types/website_collections"
import { makeWebsiteCollection } from "../util/factories/website_collections"
import { collectionsApiUrl, collectionsBaseUrl } from "../lib/urls"
import { times } from "lodash"
import { createModalState } from "../types/modal_state"
import { act } from "react-dom/test-utils"

describe("CollectionsPage", () => {
  let helper: IntegrationTestHelper,
    render: TestRenderer,
    collections: WebsiteCollection[]

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    collections = times(20, makeWebsiteCollection)

    // first page
    helper.handleRequestStub
      .withArgs(collectionsApiUrl.param({ offset: 0 }).toString(), "GET")
      .returns({
        body: {
          results:  collections.slice(0, 10),
          next:     "https://example.com",
          previous: null,
          count:    20
        },
        status: 200
      })

    // second page
    helper.handleRequestStub
      .withArgs(collectionsApiUrl.param({ offset: 10 }).toString(), "GET")
      .returns({
        body: {
          results:  collections.slice(10),
          next:     null,
          previous: "https://example.com",
          count:    20
        },
        status: 200
      })

    render = helper.configureRenderer(WebsiteCollectionsPage)
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("should render WebsiteCollection records in a list format", async () => {
    const { wrapper } = await render()
    expect(wrapper.find("li").length).toBe(10)
    expect(wrapper.find("li").map(li => li.find("a").text())).toEqual(
      collections.slice(0, 10).map(col => col.title)
    )
  })

  it("should have pagination controls, allow navigating to the second page of results", async () => {
    const { wrapper } = await render()
    expect(
      wrapper
        .find(".pagination Link.next")
        .at(0)
        .prop("to")
    ).toBe(collectionsBaseUrl.query({ offset: 10 }).toString())
  })

  it("should show a second page of results", async () => {
    helper.browserHistory.push({
      search: "offset=10"
    })
    const { wrapper } = await render()
    expect(wrapper.find("li").map(li => li.find("a").text())).toEqual(
      collections.slice(10).map(col => col.title)
    )

    expect(
      wrapper
        .find(".pagination Link.previous")
        .at(0)
        .prop("to")
    ).toBe(collectionsBaseUrl.query({ offset: 0 }).toString())
  })

  it("should let you open an editing form for a collection", async () => {
    const { wrapper } = await render()
    wrapper
      .find(".edit-collection")
      .at(0)
      .simulate("click")
    wrapper.update()
    expect(wrapper.find("BasicModal").prop("isVisible")).toBeTruthy()
    expect(wrapper.find("WebsiteCollectionEditor").prop("modalState")).toEqual(
      createModalState("editing", collections[0].id)
    )
    expect(wrapper.find("BasicModal").prop("title")).toBe("Edit")
  })

  it("should let you open a form for adding a collection", async () => {
    const { wrapper } = await render()
    wrapper.find(".blue-button.add").simulate("click")
    wrapper.update()
    expect(wrapper.find("BasicModal").prop("isVisible")).toBeTruthy()
    expect(wrapper.find("WebsiteCollectionEditor").prop("modalState")).toEqual(
      createModalState("adding", null)
    )
    expect(wrapper.find("BasicModal").prop("title")).toBe("Add")
  })

  it("should refresh after closing the modal", async () => {
    const { wrapper } = await render()
    wrapper.find(".blue-button.add").simulate("click")
    // should be able to close the modal
    act(() => {
      // @ts-ignore
      wrapper.find("BasicModal").prop("hideModal")()
    })
    wrapper.update()
    expect(wrapper.find("WebsiteCollectionEditor").prop("modalState")).toEqual(
      createModalState("closed", null)
    )
    expect(helper.handleRequestStub.args).toEqual([
      [
        collectionsApiUrl.param({ offset: 0 }).toString(),
        "GET",
        { body: undefined, credentials: undefined, headers: undefined }
      ],
      [
        collectionsApiUrl.param({ offset: 0 }).toString(),
        "GET",
        { body: undefined, credentials: undefined, headers: undefined }
      ]
    ])
  })
})
