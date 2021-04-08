const mockUseRouteMatch = jest.fn()

import React from "react"
import { act } from "react-dom/test-utils"

import SiteContentListing from "./SiteContentListing"

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
  makeSingletonsConfigItem,
  makeWebsiteContentListItem,
  makeWebsiteDetail
} from "../util/factories/websites"

import {
  RepeatableConfigItem,
  SingletonsConfigItem,
  Website,
  WebsiteContentListItem,
  WebsiteStarterConfig
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

describe("SiteContentListing", () => {
  const contentType = "sometype"
  let helper: IntegrationTestHelper,
    render: TestRenderer,
    website: Website,
    contentListingItems: WebsiteContentListItem[],
    apiResponse: WebsiteContentListingResponse,
    websiteContentDetailsLookup: Record<string, WebsiteContentListItem>

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    website = makeWebsiteDetail()
    contentListingItems = [
      makeWebsiteContentListItem(),
      makeWebsiteContentListItem()
    ]
    websiteContentDetailsLookup = {}
    for (const item of contentListingItems) {
      websiteContentDetailsLookup[item.uuid] = item
    }
  })

  afterEach(() => {
    helper.cleanup()
  })

  const setUpTestCase = (website: Website) => {
    const listingParams = { name: website.name, type: contentType, offset: 0 }
    apiResponse = {
      results:  contentListingItems,
      count:    2,
      next:     null,
      previous: null
    }
    const contentListingLookup = {
      [contentListingKey(listingParams)]: {
        ...apiResponse,
        results: apiResponse.results.map(item => item.uuid)
      }
    }
    helper.handleRequestStub
      .withArgs(
        siteApiContentListingUrl
          .param({
            name: website.name
          })
          .query({ type: contentType, offset: 0 })
          .toString(),
        "GET"
      )
      .returns({
        body:   apiResponse,
        status: 200
      })

    render = helper.configureRenderer(
      SiteContentListing,
      {
        location: {
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
  }

  describe("for repeatable items", () => {
    let configItem: RepeatableConfigItem, fullConfig: WebsiteStarterConfig

    beforeEach(() => {
      configItem = makeRepeatableConfigItem(contentType)
      fullConfig = {
        collections: [configItem]
      }
      // @ts-ignore
      website.starter.config = fullConfig
      setUpTestCase(website)
    })

    it("should render a link to the add content page", async () => {
      const params = { name: website.name, contenttype: contentType }
      mockUseRouteMatch.mockImplementation(() => ({
        params
      }))

      const { wrapper } = await render()
      expect(
        wrapper
          .find("SiteContentEditor")
          .at(1)
          .prop("visibility")
      ).toBe(false)
      const link = wrapper.find("a.add")
      expect(link.text()).toBe(`Add ${configItem.label}`)
      act(() => {
        // @ts-ignore
        link.prop("onClick")({ preventDefault: helper.sandbox.stub() })
      })
      wrapper.update()
      const component = wrapper.find("SiteContentEditor").at(1)
      expect(component.prop("uuid")).toBeNull()
      expect(component.prop("visibility")).toBe(true)

      act(() => {
        // @ts-ignore
        component.prop("toggleVisibility")()
      })
      wrapper.update()
      expect(
        wrapper
          .find("SiteContentEditor")
          .at(1)
          .prop("visibility")
      ).toBe(false)
    })

    it("should show each content item with edit links", async () => {
      const params = { name: website.name, contenttype: contentType }
      mockUseRouteMatch.mockImplementation(() => ({
        params
      }))
      for (const item of contentListingItems) {
        // when the edit button is tapped the detail view is requested, so mock each one out
        helper.handleRequestStub
          .withArgs(
            siteApiContentDetailUrl
              .param({ name: website.name, uuid: item.uuid })
              .toString(),
            "GET"
          )
          .returns({
            body:   item,
            status: 200
          })
      }

      const { wrapper } = await render()
      expect(
        wrapper
          .find("SiteContentEditor")
          .at(0)
          .prop("visibility")
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
        const component = wrapper.find("SiteContentEditor").at(0)
        expect(component.prop("uuid")).toBe(item.uuid)
        expect(component.prop("visibility")).toBe(true)

        act(() => {
          // @ts-ignore
          component.prop("toggleVisibility")()
        })
        wrapper.update()
        expect(
          wrapper
            .find("SiteContentEditor")
            .at(0)
            .prop("visibility")
        ).toBe(false)

        idx++
      }
    })
    ;[true, false].forEach(hasPrevLink => {
      [true, false].forEach(hasNextLink => {
        it(`shows the right links when there ${isIf(
          hasPrevLink
        )} a previous link and ${isIf(hasNextLink)} a next link`, async () => {
          const params = { name: website.name, contenttype: contentType }
          mockUseRouteMatch.mockImplementation(() => ({
            params
          }))
          apiResponse.next = hasNextLink ? "next" : null
          apiResponse.previous = hasPrevLink ? "prev" : null
          const startingOffset = 20
          helper.handleRequestStub
            .withArgs(
              siteApiContentListingUrl
                .param({ name: website.name })
                .query({ type: contentType, offset: startingOffset })
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
                  name: website.name,
                  contentType
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
                  name: website.name,
                  contentType
                })
                .query({ offset: startingOffset + WEBSITE_CONTENT_PAGE_SIZE })
                .toString()
            )
          }
        })
      })
    })
  })

  describe("for singleton items", () => {
    let configItem: SingletonsConfigItem, fullConfig: WebsiteStarterConfig

    beforeEach(() => {
      configItem = makeSingletonsConfigItem(contentType)
      fullConfig = {
        collections: [configItem]
      }
      // @ts-ignore
      website.starter.config = fullConfig
      setUpTestCase(website)
    })

    it("should render all config items", async () => {
      const params = { name: website.name, contenttype: contentType }
      mockUseRouteMatch.mockImplementation(() => ({
        params
      }))
      const { wrapper } = await render()
      const resultsList = wrapper.find(".ruled-list")
      expect(resultsList.exists()).toBe(true)
      const listItems = resultsList.find("li")
      for (let i = 0; i < listItems.length; i++) {
        expect(
          listItems
            .at(i)
            .find("span")
            .text()
        ).toEqual(configItem.files[i].label)
      }
    })
  })
})
