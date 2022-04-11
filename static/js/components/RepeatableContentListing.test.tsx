import React from "react"
import { act } from "react-dom/test-utils"
import { default as useIt } from "@use-it/interval"
import sinon from "sinon"
import { Route } from "react-router-dom"

import RepeatableContentListing from "./RepeatableContentListing"
import {
  GoogleDriveSyncStatuses,
} from "../constants"
import WebsiteContext from "../context/Website"

import { twoBooleanTestMatrix } from "../test_util"
import {
  siteApiContentListingUrl,
  siteApiDetailUrl,
  siteApiContentSyncGDriveUrl,
  siteContentNewUrl,
  siteContentDetailUrl
} from "../lib/urls"
import {
  contentDetailKey,
  contentListingKey,
  WebsiteContentListingResponse
} from "../query-configs/websites"
import IntegrationTestHelper, {
  TestRenderer
} from "../util/integration_test_helper"
import {
  makeRepeatableConfigItem,
  makeWebsiteContentListItem,
  makeWebsiteDetail
} from "../util/factories/websites"

import {
  RepeatableConfigItem,
  Website,
  WebsiteContentListItem
} from "../types/websites"
import { singular } from "pluralize"
import { StudioListItem } from "./StudioList"

const useInterval = useIt as jest.Mocked<typeof useIt>

// ckeditor is not working properly in tests, but we don't need to test it here so just mock it away
function mocko() {
  return <div>mock</div>
}

jest.mock("./widgets/MarkdownEditor", () => ({
  __esModule: true,
  default:    mocko
}))
jest.mock("@use-it/interval", () => ({
  __esModule: true,
  default:    jest.fn()
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
      makeWebsiteContentListItem()
    ]
    websiteContentDetailsLookup = {}
    for (const item of contentListingItems) {
      websiteContentDetailsLookup[
        contentDetailKey({ name: website.name, textId: item.text_id })
      ] = item
    }
    const listingParams = {
      name:   website.name,
      type:   configItem.name,
      offset: 0
    }
    apiResponse = {
      results:  contentListingItems,
      count:    2,
      next:     null,
      previous: null
    }
    const contentListingLookup = {
      [contentListingKey(listingParams)]: {
        ...apiResponse,
        results: apiResponse.results.map(item => item.text_id)
      }
    }
    helper.mockGetRequest(
      siteApiContentListingUrl
        .param({
          name: website.name
        })
        .query({ offset: 0, type: configItem.name })
        .toString(),
      apiResponse
    )
    helper.mockGetRequest(
      siteApiContentListingUrl
        .param({
          name: website.name
        })
        .query({ search: "search", offset: 0, type: configItem.name })
        .toString(),
      apiResponse
    )

    render = helper.configureRenderer(
      props => (
        <WebsiteContext.Provider value={website}>
          <RepeatableContentListing {...props} />
        </WebsiteContext.Provider>
      ),
      { configItem },
      {
        entities: {
          websiteDetails:        { [website.name]: website },
          websiteContentListing: contentListingLookup,
          websiteContentDetails: websiteContentDetailsLookup
        },
        queries: {}
      }
    )
    jest.useFakeTimers()
  })

  afterEach(() => {
    helper.cleanup()
    // @ts-ignore
    useInterval.mockClear()
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
            name: website.name
          })
          .query({ offset: 0, type: configItem.name })
          .toString(),
        apiResponse
      )
      const { wrapper } = await render({ configItem })
      const driveLink = wrapper.find("a.view")
      const syncLink = wrapper.find("button.sync")
      const addLink = wrapper.find("a.add")
      expect(driveLink.exists()).toBe(isGdriveEnabled && isResource)
      expect(syncLink.exists()).toBe(isGdriveEnabled && isResource)
      expect(addLink.exists()).toBe(!isGdriveEnabled || !isResource)
    }
  )

  it("Clicking the gdrive sync button should trigger a sync request", async () => {
    const postSyncStub = helper.mockPostRequest(
      siteApiContentSyncGDriveUrl
        .param({
          name: website.name
        })
        .toString(),
      {},
      200
    )
    const getStatusStub = helper.mockGetRequest(
      siteApiDetailUrl
        .param({ name: website.name })
        .query({ only_status: true })
        .toString(),
      { sync_status: "Complete" }
    )
    SETTINGS.gdrive_enabled = true
    const { wrapper } = await render()
    const syncLink = wrapper.find("button.sync")
    await act(async () => {
      // @ts-ignore
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
      target: { value: "my-search-string" }
    } as React.ChangeEvent<HTMLInputElement>
    filterInput.simulate("change", event)
    jest.runAllTimers()
    wrapper.update()
    expect(spy).toBeCalledWith("?q=my-search-string")
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
            name:        website.name,
            contentType: configItem.name,
            uuid:        item.text_id
          })
          .toString()
      )
      idx++
    }
  })

  it.only.each`
  count | initial                | prev                   | next 
  ${25} | ${""}                  | ${null}                | ${'offset=10'}
  ${25} | ${"offset=0"}          | ${null}                | ${'offset=10'}
  ${25} | ${"offset=10"}         | ${'offset=0'}          | ${'offset=20'}
  ${25} | ${"offset=7"}          | ${'offset=0'}          | ${'offset=17'}
  ${25} | ${"offset=20"}         | ${'offset=10'}         | ${null}
  ${25} | ${"offset=15"}         | ${'offset=5'}          | ${null}
  ${5}  | ${""}                  | ${null}                | ${null}
  ${25} | ${"cat=meow"}          | ${null}                | ${'cat=meow&offset=10'}
  ${25} | ${'offset=7&cat=meow'} | ${'offset=0&cat=meow'} | ${'offset=17&cat=meow'}
  `(
    "pagination uses correct offsets & preserves initial query paramswhen $count items and starting ?$initial",
    async ({ count, initial, prev, next }) => {
      const search = { initial, prev, next }
      const nextPageItems = [
        makeWebsiteContentListItem(),
        makeWebsiteContentListItem()
      ]

      const pathname = `/sites/${website.name}/type/resource/`
      helper.browserHistory.push({
        pathname: pathname,
        search:   search.initial
      })

      const initialSearch = new URLSearchParams(search.initial)
      const startingOffset = initialSearch.get("offset") ?? 0
      helper.mockGetRequest(
        siteApiContentListingUrl
          .param({ name: website.name })
          .query({ offset: startingOffset, type: configItem.name })
          .toString(),
        {
          next:     search.next ? "next" : null,
          previous: search.prev ? "prev" : null,
          count,
          results:  nextPageItems
        }
      )

      const { wrapper } = await render()
      const titles = wrapper
        .find("StudioListItem")
        .map(item => item.prop("title"))
      expect(titles).toStrictEqual(nextPageItems.map(item => item.title))

      const prevWrapper = wrapper.find(".pagination Link.previous")
      expect(prevWrapper.exists()).toBe(Boolean(search.prev))
      if (search.prev) {
        expect(prevWrapper.prop("to")).toStrictEqual({
          hash:   "",
          key:    expect.any(String),
          pathname,
          search: search.prev,
          state:  null
        })
      }

      const nextWrapper = wrapper.find(".pagination Link.next")
      expect(nextWrapper.exists()).toBe(Boolean(search.next))
      if (search.next) {
        expect(nextWrapper.prop("to")).toStrictEqual({
          hash:   "",
          key:    expect.any(String),
          pathname,
          search: search.next,
          state:  null
        })
      }
    }
  )

  test.each([true, false])(
    "should render a link to open the content editor with right label (isSingular=%p)",
    async isSingular => {
      let expectedLabel
      if (!isSingular) {
        configItem.label_singular = undefined
        expectedLabel = singular(configItem.label)
      } else {
        configItem.label_singular = expectedLabel = singular(
          configItem.label_singular as string
        )
      }
      const { wrapper } = await render()
      expect(wrapper.find("h2").text()).toBe(configItem.label)
      const link = wrapper.find(".cyan-button .add").at(1)
      expect(link.text()).toBe(`Add ${expectedLabel}`)
      expect(link.prop("href")).toBe(
        siteContentNewUrl
          .param({
            name:        website.name,
            contentType: configItem.name
          })
          .toString()
      )
    }
  )

  test.each([true, false])(
    "shows the sync status indicator",
    async gdriveEnabled => {
      SETTINGS.gdrive_enabled = gdriveEnabled
      const { wrapper } = await render({ website })
      expect(wrapper.find("DriveSyncStatusIndicator").exists()).toBe(
        gdriveEnabled
      )
    }
  )

  //
  ;[
    [GoogleDriveSyncStatuses.SYNC_STATUS_PENDING, true],
    [GoogleDriveSyncStatuses.SYNC_STATUS_PROCESSING, true],
    ["Failed", false]
  ].forEach(([status, shouldUpdate]) => {
    describe("sync status polling", () => {
      beforeEach(() => {
        website = {
          ...website,
          //@ts-ignore
          sync_status: status,
          synced_on:   "2021-01-01"
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
          { sync_status: "Complete" }
        )
        const getResourcesStub = helper.mockGetRequest(
          siteApiContentListingUrl
            .param({
              name: website.name
            })
            .query({ offset: 0, type: configItem.name })
            .toString(),
          apiResponse
        )
        await render({ website })
        // @ts-ignore
        expect(useInterval).toBeCalledTimes(2)
        // @ts-ignore
        await useInterval.mock.calls[0][0]()

        if (shouldUpdate) {
          sinon.assert.calledOnce(getStatusStub)
          sinon.assert.calledTwice(getResourcesStub)
        } else {
          sinon.assert.notCalled(getStatusStub)
          sinon.assert.calledOnce(getResourcesStub)
        }
      })
    })
  })

  test("should have a route for the EditorDrawer component ", async () => {
    const { wrapper } = await render()
    const route = wrapper.find(Route)
    expect(route.prop("path")).toEqual([
      siteContentDetailUrl.param({
        name: website.name
      }).pathname,
      siteContentNewUrl.param({
        name: website.name
      }).pathname
    ])
  })
})
