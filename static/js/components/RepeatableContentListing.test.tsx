import React from "react"
import { act } from "react-dom/test-utils"
import useInterval from "@use-it/interval"
import sinon from "sinon"

import RepeatableContentListing from "./RepeatableContentListing"
import {
  GoogleDriveSyncStatuses,
  WEBSITE_CONTENT_PAGE_SIZE
} from "../constants"
import WebsiteContext from "../context/Website"

import { isIf, shouldIf } from "../test_util"
import {
  siteApiContentDetailUrl,
  siteContentListingUrl,
  siteApiContentListingUrl,
  siteApiDetailUrl,
  siteApiContentSyncGDriveUrl
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
import { createModalState } from "../types/modal_state"

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

    render = helper.configureRenderer(
      props => (
        <WebsiteContext.Provider value={website}>
          <RepeatableContentListing {...props} />
        </WebsiteContext.Provider>
      ),
      {
        configItem: configItem,
        location:   {
          search: ""
        }
      },
      {
        entities: {
          websiteDetails:        { [website.name]: website },
          websiteContentListing: contentListingLookup,
          websiteContentDetails: websiteContentDetailsLookup
        },
        queries: {}
      }
    )
  })

  afterEach(() => {
    helper.cleanup()
    // @ts-ignore
    useInterval.mockClear()
  })
  ;[true, false].forEach(isGdriveEnabled => {
    [true, false].forEach(isResource => {
      it(`${shouldIf(
        isGdriveEnabled && isResource
      )} show the gdrive links when gdriveis ${isGdriveEnabled} and isResource is ${isResource}`, async () => {
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
        const addLink = wrapper.find("button.add")
        expect(driveLink.exists()).toBe(isGdriveEnabled && isResource)
        expect(syncLink.exists()).toBe(isGdriveEnabled && isResource)
        expect(addLink.exists()).toBe(!isGdriveEnabled || !isResource)
      })
    })
  })

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

  it("should render a button to open the content editor", async () => {
    const { wrapper } = await render()
    expect(
      wrapper
        .find("BasicModal")
        .at(0)
        .prop("isVisible")
    ).toBe(false)
    const link = wrapper.find("button.add")
    expect(link.text()).toBe(`Add ${configItem.label_singular}`)
    act(() => {
      // @ts-ignore
      link.prop("onClick")({ preventDefault: helper.sandbox.stub() })
    })
    wrapper.update()
    const editorModal = wrapper.find("BasicModal").at(0)
    const siteContentEditor = editorModal.find("SiteContentEditor")
    expect(siteContentEditor.prop("editorState")).toEqual(
      createModalState("adding")
    )
    expect(editorModal.prop("isVisible")).toBe(true)

    act(() => {
      // @ts-ignore
      siteContentEditor.prop("hideModal")()
    })
    wrapper.update()
    expect(
      wrapper
        .find("BasicModal")
        .at(0)
        .prop("isVisible")
    ).toBe(false)
  })

  it("should show each content item with edit links", async () => {
    for (const item of contentListingItems) {
      // when the edit button is tapped the detail view is requested, so mock each one out
      helper.mockGetRequest(
        siteApiContentDetailUrl
          .param({ name: website.name, textId: item.text_id })
          .toString(),
        item
      )
    }

    const { wrapper } = await render()

    expect(
      wrapper
        .find("BasicModal")
        .at(0)
        .prop("isVisible")
    ).toBe(false)

    let idx = 0
    for (const item of contentListingItems) {
      const li = wrapper.find("li").at(idx)
      expect(li.text()).toContain(item.title)
      act(() => {
        // @ts-ignore
        li.prop("onClick")({ preventDefault: helper.sandbox.stub() })
      })
      wrapper.update()
      const editorModal = wrapper.find("BasicModal").at(0)
      const siteContentEditor = editorModal.find("SiteContentEditor")
      expect(siteContentEditor.prop("editorState")).toEqual(
        createModalState("editing", item.text_id)
      )
      expect(editorModal.prop("isVisible")).toBe(true)

      act(() => {
        // @ts-ignore
        siteContentEditor.prop("hideModal")()
      })
      wrapper.update()
      expect(
        wrapper
          .find("BasicModal")
          .at(0)
          .prop("isVisible")
      ).toBe(false)

      idx++
    }
  })

  //
  ;[true, false].forEach(hasPrevLink => {
    [true, false].forEach(hasNextLink => {
      it(`shows the right links when there ${isIf(
        hasPrevLink
      )} a previous link and ${isIf(hasNextLink)} a next link`, async () => {
        apiResponse.next = hasNextLink ? "next" : null
        apiResponse.previous = hasPrevLink ? "prev" : null
        const startingOffset = 20
        const nextPageItems = [
          makeWebsiteContentListItem(),
          makeWebsiteContentListItem()
        ]
        helper.mockGetRequest(
          siteApiContentListingUrl
            .param({ name: website.name })
            .query({ offset: startingOffset, type: configItem.name })
            .toString(),
          {
            next:     hasNextLink ? "next" : null,
            previous: hasPrevLink ? "prev" : null,
            count:    2,
            results:  nextPageItems
          }
        )

        helper.browserHistory.push({ search: `offset=${startingOffset}` })

        const { wrapper } = await render()
        const titles = wrapper
          .find("StudioListItem")
          .map(item => item.prop("title"))
        expect(titles).toStrictEqual(nextPageItems.map(item => item.title))

        const prevWrapper = wrapper.find(".pagination Link.previous")
        expect(prevWrapper.exists()).toBe(hasPrevLink)
        if (hasPrevLink) {
          expect(prevWrapper.prop("to")).toBe(
            siteContentListingUrl
              .param({
                name:        website.name,
                contentType: configItem.name
              })
              .query({
                offset: startingOffset - WEBSITE_CONTENT_PAGE_SIZE
              })
              .toString()
          )
        }

        const nextWrapper = wrapper.find(".pagination Link.next")
        expect(nextWrapper.exists()).toBe(hasNextLink)
        if (hasNextLink) {
          expect(nextWrapper.prop("to")).toBe(
            siteContentListingUrl
              .param({
                name:        website.name,
                contentType: configItem.name
              })
              .query({ offset: startingOffset + WEBSITE_CONTENT_PAGE_SIZE })
              .toString()
          )
        }
      })
    })
  })

  //
  ;[true, false].forEach(isSingular => {
    it("should use the singular label where appropriate", async () => {
      let expectedLabel
      if (!isSingular) {
        configItem.label_singular = undefined
        expectedLabel = configItem.label
      } else {
        expectedLabel = configItem.label_singular
      }
      const { wrapper } = await render()
      expect(wrapper.find("h2").text()).toBe(configItem.label)
      expect(wrapper.find("button.add").text()).toBe(`Add ${expectedLabel}`)
      act(() => {
        const event: any = { preventDefault: jest.fn() }
        const button = wrapper.find("button.add")
        // @ts-ignore
        button.prop("onClick")(event)
      })
      wrapper.update()
      expect(
        wrapper
          .find("BasicModal")
          .at(0)
          .prop("title")
      ).toBe(`Add ${expectedLabel}`)
    })
  })
  //
  ;[true, false].forEach(gdriveEnabled => {
    it("shows the sync status indicator", async () => {
      SETTINGS.gdrive_enabled = gdriveEnabled
      const { wrapper } = await render({ website })
      expect(wrapper.find("DriveSyncStatusIndicator").exists()).toBe(
        gdriveEnabled
      )
    })
  })
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
})
