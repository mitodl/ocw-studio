const mockUseRouteMatch = jest.fn()

import React from "react"
import { act } from "react-dom/test-utils"

import RepeatableContentListing from "./RepeatableContentListing"

import { isIf } from "../test_util"
import {
  siteApiContentDetailUrl,
  siteContentListingUrl,
  siteApiContentListingUrl
} from "../lib/urls"
import {
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
import { WEBSITE_CONTENT_PAGE_SIZE } from "../constants"

jest.mock("react-router-dom", () => ({
  // @ts-ignore
  ...jest.requireActual("react-router-dom"),
  useRouteMatch: mockUseRouteMatch
}))

// ckeditor is not working properly in tests, but we don't need to test it here so just mock it away
function mocko() {
  return <div>mock</div>
}

jest.mock("./widgets/MarkdownEditor", () => ({
  __esModule: true,
  default:    mocko
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
    configItem = makeRepeatableConfigItem()
    contentListingItems = [
      makeWebsiteContentListItem(),
      makeWebsiteContentListItem()
    ]
    websiteContentDetailsLookup = {}
    for (const item of contentListingItems) {
      websiteContentDetailsLookup[item.text_id] = item
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
    helper.handleRequestStub
      .withArgs(
        siteApiContentListingUrl
          .param({
            name: website.name
          })
          .query({ type: configItem.name, offset: 0 })
          .toString(),
        "GET"
      )
      .returns({
        body:   apiResponse,
        status: 200
      })

    render = helper.configureRenderer(
      RepeatableContentListing,
      {
        website:    website,
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
  })

  it("should render a link to the add content page", async () => {
    const { wrapper } = await render()
    expect(wrapper.find("BasicModal").prop("isVisible")).toBe(false)
    const link = wrapper.find("a.add")
    expect(link.text()).toBe(`Add ${configItem.label}`)
    act(() => {
      // @ts-ignore
      link.prop("onClick")({ preventDefault: helper.sandbox.stub() })
    })
    wrapper.update()
    const editorModal = wrapper.find("BasicModal")
    const siteContentEditor = editorModal.find("SiteContentEditor")
    expect(siteContentEditor.prop("textId")).toBeNull()
    expect(editorModal.prop("isVisible")).toBe(true)

    act(() => {
      // @ts-ignore
      siteContentEditor.prop("hideModal")()
    })
    wrapper.update()
    expect(wrapper.find("BasicModal").prop("isVisible")).toBe(false)
  })

  it("should show each content item with edit links", async () => {
    for (const item of contentListingItems) {
      // when the edit button is tapped the detail view is requested, so mock each one out
      helper.handleRequestStub
        .withArgs(
          siteApiContentDetailUrl
            .param({ name: website.name, textId: item.text_id })
            .toString(),
          "GET"
        )
        .returns({
          body:   item,
          status: 200
        })
    }

    const { wrapper } = await render()
    expect(wrapper.find("BasicModal").prop("isVisible")).toBe(false)

    let idx = 0
    for (const item of contentListingItems) {
      const li = wrapper.find("li").at(idx)
      expect(li.text()).toContain(item.title)
      act(() => {
        // @ts-ignore
        li.prop("onClick")({ preventDefault: helper.sandbox.stub() })
      })
      wrapper.update()
      const editorModal = wrapper.find("BasicModal")
      const siteContentEditor = editorModal.find("SiteContentEditor")
      expect(siteContentEditor.prop("textId")).toBe(item.text_id)
      expect(editorModal.prop("isVisible")).toBe(true)

      act(() => {
        // @ts-ignore
        siteContentEditor.prop("hideModal")()
      })
      wrapper.update()
      expect(wrapper.find("BasicModal").prop("isVisible")).toBe(false)

      idx++
    }
  })
  ;[true, false].forEach(hasPrevLink => {
    [true, false].forEach(hasNextLink => {
      it(`shows the right links when there ${isIf(
        hasPrevLink
      )} a previous link and ${isIf(hasNextLink)} a next link`, async () => {
        apiResponse.next = hasNextLink ? "next" : null
        apiResponse.previous = hasPrevLink ? "prev" : null
        const startingOffset = 20
        helper.handleRequestStub
          .withArgs(
            siteApiContentListingUrl
              .param({ name: website.name })
              .query({ type: configItem.name, offset: startingOffset })
              .toString(),
            "GET"
          )
          .returns({
            body:   apiResponse,
            status: 200
          })

        helper.browserHistory.push({ search: `offset=${startingOffset}` })

        const { wrapper } = await render()

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
})
