import React from "react"
import { act } from "react-dom/test-utils"
import { default as useIt } from "@use-it/interval"
import sinon from "sinon"
import * as rrDOM from "react-router-dom"

import RepeatableContentListing from "./RepeatableContentListing"
import {
  GoogleDriveSyncStatuses,
  WEBSITE_CONTENT_PAGE_SIZE
} from "../constants"
import WebsiteContext from "../context/Website"

import useConfirmation from "../hooks/confirmation"
import { twoBooleanTestMatrix } from "../test_util"
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
import configureStore from "../store/configureStore"
import { singular } from "pluralize"

const { useLocation } = rrDOM as jest.Mocked<typeof rrDOM>
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
jest.mock("../hooks/confirmation", () => ({
  __esModule: true,
  default:    jest.fn()
}))
jest.mock("react-router-dom", () => ({
  __esModule:  true,
  ...jest.requireActual("react-router-dom"),
  useLocation: jest.fn()
}))

describe("RepeatableContentListing", () => {
  let helper: IntegrationTestHelper,
    render: TestRenderer,
    website: Website,
    configItem: RepeatableConfigItem,
    contentListingItems: WebsiteContentListItem[],
    apiResponse: WebsiteContentListingResponse,
    websiteContentDetailsLookup: Record<string, WebsiteContentListItem>,
    setConfirmationModalVisible: any,
    conditionalClose: any

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
    setConfirmationModalVisible = jest.fn()
    conditionalClose = jest.fn()
    // @ts-ignore
    useConfirmation.mockClear()
    // @ts-ignore
    useConfirmation.mockReturnValue({
      confirmationModalVisible: false,
      setConfirmationModalVisible,
      conditionalClose
    })
    useLocation.mockClear()
    // @ts-ignore
    useLocation.mockReturnValue({ pathname: "/path/to/pages" })

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
      const addLink = wrapper.find("button.add")
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

  it("should render a button to open the content editor", async () => {
    const { wrapper } = await render()
    expect(
      wrapper
        .find("BasicModal")
        .at(1)
        .prop("isVisible")
    ).toBe(false)
    const link = wrapper.find("button.add")
    expect(link.text()).toBe(`Add ${configItem.label_singular}`)
    act(() => {
      // @ts-ignore
      link.prop("onClick")({ preventDefault: helper.sandbox.stub() })
    })
    wrapper.update()
    const editorModal = wrapper.find("BasicModal").at(1)
    const siteContentEditor = editorModal.find("SiteContentEditor")
    expect(siteContentEditor.prop("editorState")).toEqual(
      createModalState("adding")
    )
    expect(editorModal.prop("isVisible")).toBe(true)

    act(() => {
      // @ts-ignore
      siteContentEditor.prop("dismiss")()
    })
    wrapper.update()
    expect(
      wrapper
        .find("BasicModal")
        .at(0)
        .prop("isVisible")
    ).toBe(false)
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
        .at(1)
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
      const editorModal = wrapper.find("BasicModal").at(1)
      const siteContentEditor = editorModal.find("SiteContentEditor")
      expect(siteContentEditor.prop("editorState")).toEqual(
        createModalState("editing", item.text_id)
      )
      expect(editorModal.prop("isVisible")).toBe(true)

      act(() => {
        // @ts-ignore
        siteContentEditor.prop("dismiss")()
      })
      expect(conditionalClose).toBeCalledWith(true)

      idx++
    }
  })

  test.each(twoBooleanTestMatrix)(
    "shows the right links when there hasPrevLink=%p and hasNextLink=%p",
    async (hasNextLink, hasPrevLink) => {
      apiResponse.next = hasNextLink ? "next" : null
      apiResponse.previous = hasPrevLink ? "prev" : null
      const startingOffset = 20
      const nextPageItems = [
        makeWebsiteContentListItem(),
        makeWebsiteContentListItem()
      ]

      helper.browserHistory.push(`/?offset=${startingOffset}`)
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
    }
  )

  test.each([true, false])(
    "should use the singular label when appropriate (isSingular=%p)",
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
          .at(1)
          .prop("title")
      ).toBe(`Add ${expectedLabel}`)
    }
  )

  it("sets a dirty flag", async () => {
    const { wrapper } = await render({ website })
    expect(wrapper.find("ConfirmationModal").prop("dirty")).toBeFalsy()
    const setDirty =
      // @ts-ignore
      useConfirmation.mock.calls[useConfirmation.mock.calls.length - 1][0]
        .setDirty
    act(() => setDirty(true))
    wrapper.update()
    expect(wrapper.find("ConfirmationModal").prop("dirty")).toBeTruthy()
  })

  it("clears a dirty flag when the path changes", async () => {
    const { wrapper } = await render({ website })
    expect(wrapper.find("ConfirmationModal").prop("dirty")).toBeFalsy()
    const setDirty =
      // @ts-ignore
      useConfirmation.mock.calls[useConfirmation.mock.calls.length - 1][0]
        .setDirty
    act(() => setDirty(true))
    // @ts-ignore
    useLocation.mockReturnValue({
      pathname: "/resources"
    })

    // force a rerender so it picks up the changed location
    await wrapper.setProps({
      store: configureStore({ entities: {}, queries: {} })
    })

    // @ts-ignore
    wrapper.update()
    expect(wrapper.find("ConfirmationModal").prop("dirty")).toBeFalsy()
  })

  it("uses visibility from useConfirmation", async () => {
    // @ts-ignore
    useConfirmation.mockReturnValue({
      confirmationModalVisible: true,
      setConfirmationModalVisible,
      conditionalClose
    })
    const { wrapper } = await render({ website })
    expect(
      wrapper.find("ConfirmationModal").prop("confirmationModalVisible")
    ).toBeTruthy()
  })

  it("passes closeContentDrawer to useConfirmation", async () => {
    const { wrapper } = await render()
    expect(
      wrapper
        .find("BasicModal")
        .at(1)
        .prop("isVisible")
    ).toBe(false)
    const link = wrapper.find("button.add")
    act(() => {
      // @ts-ignore
      link.prop("onClick")({ preventDefault: helper.sandbox.stub() })
    })
    wrapper.update()
    expect(
      wrapper
        .find("BasicModal")
        .at(1)
        .prop("isVisible")
    ).toBe(true)

    act(() => {
      // @ts-ignore
      useConfirmation.mock.calls[0][0].close()
    })
    wrapper.update()
    expect(
      wrapper
        .find("BasicModal")
        .at(1)
        .prop("isVisible")
    ).toBe(false)
  })

  it("sets visibility on the confirmation modal", async () => {
    const { wrapper } = await render({ website })
    const setVisible = wrapper
      .find("ConfirmationModal")
      .prop("setConfirmationModalVisible")
    // @ts-ignore
    act(() => setVisible(true))
    expect(setConfirmationModalVisible).toBeCalledWith(true)
  })

  it("dismisses a modal", async () => {
    const { wrapper } = await render({ website })
    act(() => {
      // @ts-ignore
      wrapper.find("ConfirmationModal").prop("dismiss")()
    })
    expect(conditionalClose).toBeCalledWith(true)
  })

  it("hides the drawer, maybe with a confirmation dialog first", async () => {
    const { wrapper } = await render({ website })
    act(() => {
      // @ts-ignore
      wrapper
        .find("BasicModal")
        .at(1)
        .prop("hideModal")()
    })
    expect(conditionalClose).toBeCalledWith(false)
  })

  it("dismisses a modal from the editor", async () => {
    const { wrapper } = await render()
    const link = wrapper.find("button.add")
    act(() => {
      // @ts-ignore
      link.prop("onClick")({ preventDefault: helper.sandbox.stub() })
    })
    wrapper.update()
    // @ts-ignore
    const editorModal = wrapper.find("BasicModal").at(1)
    wrapper.update()
    const siteContentEditor = editorModal.find("SiteContentEditor")
    // @ts-ignore
    act(() => {
      // @ts-ignore
      siteContentEditor.prop("dismiss")()
    })

    expect(conditionalClose).toBeCalledWith(true)
  })

  it("passes setDirty to SiteContentEditor", async () => {
    const { wrapper } = await render()
    const link = wrapper.find("button.add")
    act(() => {
      // @ts-ignore
      link.prop("onClick")({ preventDefault: helper.sandbox.stub() })
    })
    wrapper.update()
    // @ts-ignore
    const editorModal = wrapper.find("BasicModal").at(1)
    wrapper.update()
    const siteContentEditor = editorModal.find("SiteContentEditor")
    const setDirty =
      // @ts-ignore
      useConfirmation.mock.calls[useConfirmation.mock.calls.length - 1][0]
        .setDirty
    expect(siteContentEditor.prop("setDirty")).toBe(setDirty)
  })

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
})
