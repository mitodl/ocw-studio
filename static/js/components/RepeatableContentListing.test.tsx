import React from "react"
import { act } from "react-dom/test-utils"
import { default as useInterval } from "@use-it/interval"
import sinon from "sinon"
import { Route } from "react-router-dom"

import RepeatableContentListing from "./RepeatableContentListing"
import { GoogleDriveSyncStatuses } from "../constants"
import WebsiteContext from "../context/Website"

import { twoBooleanTestMatrix } from "../test_util"
import {
  siteApiContentListingUrl,
  siteApiDetailUrl,
  siteApiContentSyncGDriveUrl,
  siteContentNewUrl,
  siteContentDetailUrl,
  siteApiContentDetailUrl,
} from "../lib/urls"
import {
  contentDetailKey,
  contentListingKey,
  WebsiteContentListingResponse,
} from "../query-configs/websites"
import IntegrationTestHelper, {
  TestRenderer,
} from "../util/integration_test_helper_old"
import {
  makeRepeatableConfigItem,
  makeWebsiteContentListItem,
  makeWebsiteDetail,
} from "../util/factories/websites"

import {
  RepeatableConfigItem,
  Website,
  WebsiteContentListItem,
} from "../types/websites"
import { singular } from "pluralize"
import { StudioListItem } from "./StudioList"

const spyUseInterval = jest.mocked(useInterval)

// ckeditor is not working properly in tests, but we don't need to test it here so just mock it away
function mocko() {
  return <div>mock</div>
}

jest.mock("./widgets/MarkdownEditor", () => ({
  __esModule: true,
  default: mocko,
}))
jest.mock("@use-it/interval", () => ({
  __esModule: true,
  default: jest.fn(),
}))

describe("RepeatableContentListing", () => {
  let helper: IntegrationTestHelper,
    render: TestRenderer,
    website: Website,
    configItem: RepeatableConfigItem,
    contentListingItems: WebsiteContentListItem[],
    apiResponse: WebsiteContentListingResponse,
    websiteContentDetailsLookup: Record<string, WebsiteContentListItem>

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    website = makeWebsiteDetail()
    configItem = makeRepeatableConfigItem("resource")
    contentListingItems = [
      makeWebsiteContentListItem(),
      makeWebsiteContentListItem(),
    ]
    websiteContentDetailsLookup = {}
    for (const item of contentListingItems) {
      websiteContentDetailsLookup[
        contentDetailKey({ name: website.name, textId: item.text_id })
      ] = item
    }
    const listingParams = {
      name: website.name,
      type: configItem.name,
      offset: 0,
    }
    apiResponse = {
      results: contentListingItems,
      count: 2,
      next: null,
      previous: null,
    }
    const contentListingLookup = {
      [contentListingKey(listingParams)]: {
        ...apiResponse,
        results: apiResponse.results.map((item) => item.text_id),
      },
    }
    helper.mockGetRequest(
      siteApiContentListingUrl
        .param({
          name: website.name,
        })
        .query({ offset: 0, type: configItem.name })
        .toString(),
      apiResponse,
    )
    helper.mockGetRequest(
      siteApiContentListingUrl
        .param({
          name: website.name,
        })
        .query({ search: "search", offset: 0, type: configItem.name })
        .toString(),
      apiResponse,
    )

    render = helper.configureRenderer(
      (props) => (
        <WebsiteContext.Provider value={website}>
          <RepeatableContentListing {...props} />
        </WebsiteContext.Provider>
      ),
      { configItem },
      {
        entities: {
          websiteDetails: { [website.name]: website },
          websiteContentListing: contentListingLookup,
          websiteContentDetails: websiteContentDetailsLookup,
        },
        queries: {},
      },
    )
    jest.useFakeTimers()
  })

  afterEach(() => {
    helper.cleanup()
    spyUseInterval.mockClear()
    jest.useRealTimers()
  })

  test.each(twoBooleanTestMatrix)(
    "showing gdrive links when gdriveis=%p and isResource=%p",
    async (isGdriveEnabled, isResource) => {
      SETTINGS.gdrive_enabled = isGdriveEnabled
      configItem = makeRepeatableConfigItem(isResource ? "resource" : "page")
      helper.mockGetRequest(
        siteApiContentListingUrl
          .param({
            name: website.name,
          })
          .query({ offset: 0, type: configItem.name })
          .toString(),
        apiResponse,
      )
      const { wrapper } = await render({ configItem })
      const driveLink = wrapper.find("a.view")
      const syncLink = wrapper.find("button.sync")
      const addLink = wrapper.find("a.add")
      expect(driveLink.exists()).toBe(isGdriveEnabled && isResource)
      expect(syncLink.exists()).toBe(isGdriveEnabled && isResource)
      expect(addLink.exists()).toBe(!isGdriveEnabled || !isResource)
    },
  )

  it("Clicking the gdrive sync button should trigger a sync request", async () => {
    const postSyncStub = helper.mockPostRequest(
      siteApiContentSyncGDriveUrl
        .param({
          name: website.name,
        })
        .toString(),
      {},
      200,
    )
    const getStatusStub = helper.mockGetRequest(
      siteApiDetailUrl
        .param({ name: website.name })
        .query({ only_status: true })
        .toString(),
      { sync_status: "Complete" },
    )
    SETTINGS.gdrive_enabled = true
    const { wrapper } = await render()
    const syncLink = wrapper.find("button.sync")
    await act(async () => {
      // @ts-expect-error Not mocking whole object
      syncLink.prop("onClick")({ preventDefault: helper.sandbox.stub() })
    })
    expect(postSyncStub.called).toBeTruthy()
    expect(getStatusStub.called).toBeTruthy()
  })

  test("should filter based on query param", async () => {
    helper.browserHistory.push("/?q=search")
    const { wrapper } = await render()
    contentListingItems.forEach((item, idx) => {
      const li = wrapper.find("li").at(idx)
      expect(li.text()).toContain(item.title)
    })
  })

  test("should let the user filter via text input", async () => {
    const spy = jest.spyOn(helper.browserHistory, "push")
    const { wrapper } = await render()
    const filterInput = wrapper.find(".site-search-input")
    const event = {
      // eslint-disable-next-line @typescript-eslint/no-empty-function
      preventDefault() {},
      target: { value: "my-search-string" },
    } as React.ChangeEvent<HTMLInputElement>
    filterInput.simulate("change", event)
    jest.runAllTimers()
    wrapper.update()
    expect(spy).toHaveBeenCalledWith("?q=my-search-string")
  })

  const deletableTestCases = [
    { name: "external resource", configName: "external-resource" },
    { name: "instructor", configName: "instructor" },
  ]
  deletableTestCases.forEach(({ name, configName }) => {
    it(`should delete ${name}`, async () => {
      const configItem = makeRepeatableConfigItem(configName)
      const contentItem = makeWebsiteContentListItem()
      websiteContentDetailsLookup = {
        [contentDetailKey({
          name: website.name,
          textId: contentItem.text_id,
        })]: contentItem,
      }
      const apiResponse = {
        results: [contentItem],
        count: 1,
        next: null,
        previous: null,
      }
      const contentListingLookup = {
        [contentListingKey({
          name: website.name,
          type: configItem.name,
          offset: 0,
        })]: {
          ...apiResponse,
          results: apiResponse.results.map((item) => item.text_id),
        },
      }
      helper.mockGetRequest(
        siteApiContentListingUrl
          .param({
            name: website.name,
          })
          .query({ offset: 0, type: configItem.name })
          .toString(),
        apiResponse,
      )
      render = helper.configureRenderer(
        (props) => (
          <WebsiteContext.Provider value={website}>
            <RepeatableContentListing {...props} />
          </WebsiteContext.Provider>
        ),
        { configItem: configItem },
        {
          entities: {
            websiteDetails: { [website.name]: website },
            websiteContentListing: contentListingLookup,
            websiteContentDetails: websiteContentDetailsLookup,
          },
          queries: {},
        },
      )
      const contentItemToDelete = contentItem
      const getStatusStub = helper.mockGetRequest(
        siteApiDetailUrl
          .param({ name: website.name })
          .query({ only_status: true })
          .toString(),
        { sync_status: "Complete" },
      )
      const deleteContentStub = helper.mockDeleteRequest(
        siteApiContentDetailUrl
          .param({
            name: website.name,
            textId: contentItemToDelete.text_id,
          })
          .toString(),
        {},
      )
      const { wrapper } = await render()
      wrapper.find(".transparent-button").at(0).simulate("click")
      wrapper.update()
      act(() => {
        wrapper.find("button.dropdown-item").at(0).simulate("click")
      })
      wrapper.update()
      let dialog = wrapper.find("Dialog")
      expect(dialog.prop("open")).toBe(true)
      expect(dialog.prop("bodyContent")).toContain(contentItemToDelete.title)

      // Confirm the deletion in the dialog
      await act(async () => {
        dialog.find("ModalFooter").find("button").at(1).simulate("click")
      })
      wrapper.update()

      // Assert the DELETE request was called
      sinon.assert.calledOnce(deleteContentStub)

      // Assert the GET request for website status was called
      sinon.assert.calledOnce(getStatusStub)

      // Assert the dialog is closed
      dialog = wrapper.find("Dialog")
      expect(dialog.prop("open")).toBe(false)
    })
  })

  it("should show each content item with edit links", async () => {
    const { wrapper } = await render()

    let idx = 0
    for (const item of contentListingItems) {
      const listItem = wrapper.find(StudioListItem).at(idx)
      expect(listItem.prop("title")).toBe(item.title)
      expect(listItem.prop("to")).toBe(
        siteContentDetailUrl
          .param({
            name: website.name,
            contentType: configItem.name,
            uuid: item.text_id,
          })
          .toString(),
      )
      idx++
    }
  })

  describe("pagination", () => {
    /**
     *
     * @param count  total number of items to paginate
     * @param queryInitial initial route query param
     * @returns Wrappers for the current page and next/prev buttons, as well
     * as the route pathname
     */
    const setupRouteAndMock = async (count: number, queryInitial: string) => {
      const pageItems = [
        makeWebsiteContentListItem(),
        makeWebsiteContentListItem(),
      ]

      const pathname = `/sites/${website.name}/type/resource/`
      helper.browserHistory.push({
        pathname: pathname,
        search: queryInitial,
      })

      const initialSearch = new URLSearchParams(queryInitial)
      const startingOffset = initialSearch.get("offset") ?? 0
      helper.mockGetRequest(
        siteApiContentListingUrl
          .param({ name: website.name })
          .query({ offset: startingOffset, type: configItem.name })
          .toString(),
        {
          count,
          results: pageItems,
        },
      )
      const { wrapper } = await render()

      const prevLink = wrapper.find(".pagination Link.previous")
      const nextLink = wrapper.find(".pagination Link.next")
      return {
        wrappers: { currentPage: wrapper, prevLink, nextLink },
        pathname,
      }
    }

    it.each([
      { count: 25, search: ["", "offset=10"] },
      { count: 25, search: ["offset=0", "offset=10"] },
      { count: 25, search: ["cat=meow", "cat=meow&offset=10"] },
    ])(
      'shows only a "Next" button when appropriate',
      async ({ count, search }) => {
        const [initial, next] = search
        const { wrappers, pathname } = await setupRouteAndMock(count, initial)

        expect(wrappers.prevLink.exists()).toBe(false)
        expect(wrappers.nextLink.exists()).toBe(true)

        expect(wrappers.nextLink.prop("to")).toStrictEqual({
          hash: "",
          key: expect.any(String),
          pathname,
          search: next,
        })
      },
    )

    it.each([
      { count: 25, search: ["offset=20", "offset=10"] },
      { count: 25, search: ["offset=15", "offset=5"] },
      { count: 25, search: ["cat=meow&offset=20", "cat=meow&offset=10"] },
    ])(
      'shows only a "Previous" button when appropriate',
      async ({ count, search }) => {
        const [initial, previous] = search
        const { wrappers, pathname } = await setupRouteAndMock(count, initial)

        expect(wrappers.prevLink.exists()).toBe(true)
        expect(wrappers.nextLink.exists()).toBe(false)

        expect(wrappers.prevLink.prop("to")).toStrictEqual({
          hash: "",
          key: expect.any(String),
          pathname,
          search: previous,
        })
      },
    )

    it.each([
      { count: 25, search: ["offset=10", "offset=0", "offset=20"] },
      { count: 25, search: ["offset=7", "offset=0", "offset=17"] },
      {
        count: 25,
        search: [
          "cat=meow&offset=14",
          "cat=meow&offset=4",
          "cat=meow&offset=24",
        ],
      },
    ])(
      'shows both "Previous" and "Next" buttons when appropriate',
      async ({ count, search }) => {
        const [initial, previous, next] = search
        const { wrappers, pathname } = await setupRouteAndMock(count, initial)

        expect(wrappers.prevLink.exists()).toBe(true)
        expect(wrappers.nextLink.exists()).toBe(true)

        expect(wrappers.prevLink.prop("to")).toStrictEqual({
          hash: "",
          key: expect.any(String),
          pathname,
          search: previous,
        })
        expect(wrappers.nextLink.prop("to")).toStrictEqual({
          hash: "",
          key: expect.any(String),
          pathname,
          search: next,
        })
      },
    )

    it.each([{ count: 5, search: [""] }])(
      'shows neither "Previous" nor "Next" buttons when appropriate',
      async ({ count, search }) => {
        const [initial] = search
        const { wrappers } = await setupRouteAndMock(count, initial)

        expect(wrappers.prevLink.exists()).toBe(false)
        expect(wrappers.nextLink.exists()).toBe(false)
      },
    )
  })

  test.each([true, false])(
    "should render a link to open the content editor with right label (isSingular=%p)",
    async (isSingular) => {
      let expectedLabel
      if (!isSingular) {
        configItem.label_singular = undefined
        expectedLabel = singular(configItem.label)
      } else {
        configItem.label_singular = expectedLabel = singular(
          configItem.label_singular as string,
        )
      }
      const { wrapper } = await render()
      expect(wrapper.find("h2").text()).toBe(configItem.label)
      const link = wrapper.find(".cyan-button .add").at(1)
      expect(link.text()).toBe(`Add ${expectedLabel}`)
      expect(link.prop("href")).toBe(
        siteContentNewUrl
          .param({
            name: website.name,
            contentType: configItem.name,
          })
          .toString(),
      )
    },
  )

  test.each([true, false])(
    "shows the sync status indicator",
    async (gdriveEnabled) => {
      SETTINGS.gdrive_enabled = gdriveEnabled
      const { wrapper } = await render({ website })
      expect(wrapper.find("DriveSyncStatusIndicator").exists()).toBe(
        gdriveEnabled,
      )
    },
  )

  describe.each([
    {
      status: GoogleDriveSyncStatuses.SYNC_STATUS_PENDING,
      shouldUpdate: true,
    },
    {
      status: GoogleDriveSyncStatuses.SYNC_STATUS_PROCESSING,
      shouldUpdate: true,
    },
    {
      status: GoogleDriveSyncStatuses.SYNC_STATUS_FAILED,
      shouldUpdate: false,
    },
  ])("sync status polling", ({ status, shouldUpdate }) => {
    beforeEach(() => {
      website = {
        ...website,
        sync_status: status,
        synced_on: "2021-01-01",
      }
    })

    it(`${
      shouldUpdate ? "polls" : "doesn't poll"
    } the website sync status when sync_status=${status}`, async () => {
      SETTINGS.gdrive_enabled = true
      const getStatusStub = helper.mockGetRequest(
        siteApiDetailUrl
          .param({ name: website.name })
          .query({ only_status: true })
          .toString(),
        { sync_status: "Complete" },
      )
      const getResourcesStub = helper.mockGetRequest(
        siteApiContentListingUrl
          .param({
            name: website.name,
          })
          .query({ offset: 0, type: configItem.name })
          .toString(),
        apiResponse,
      )
      await render({ website })
      expect(spyUseInterval).toHaveBeenCalledTimes(2)
      await spyUseInterval.mock.calls[0][0]()

      if (shouldUpdate) {
        sinon.assert.calledOnce(getStatusStub)
        sinon.assert.calledTwice(getResourcesStub)
      } else {
        sinon.assert.notCalled(getStatusStub)
        sinon.assert.calledOnce(getResourcesStub)
      }
    })
  })

  test("should have a route for the EditorDrawer component", async () => {
    const { wrapper } = await render()
    const listing = wrapper.find(RepeatableContentListing)
    const route = listing.find(Route)
    expect(route.prop("path")).toEqual([
      siteContentDetailUrl.param({
        name: website.name,
      }).pathname,
      siteContentNewUrl.param({
        name: website.name,
      }).pathname,
    ])
  })
})
