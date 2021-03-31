const mockUseRouteMatch = jest.fn()

import React from "react"
import { act } from "react-dom/test-utils"

import SiteContentListing from "./SiteContentListing"

import { isIf } from "../test_util"
import {
  siteAddContentUrl,
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
  makeWebsiteContentListItem,
  makeWebsiteDetail
} from "../util/factories/websites"

import { Website, WebsiteContentListItem } from "../types/websites"
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
  let helper: IntegrationTestHelper,
    render: TestRenderer,
    website: Website,
    contentType: string,
    contentListingItems: WebsiteContentListItem[],
    response: WebsiteContentListingResponse

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    website = makeWebsiteDetail()
    const websitesLookup = { [website.name]: website }
    contentListingItems = [
      makeWebsiteContentListItem(),
      makeWebsiteContentListItem()
    ]
    response = {
      results:  contentListingItems,
      count:    2,
      next:     null,
      previous: null
    }
    // @ts-ignore
    contentType = website.starter?.config?.collections[0].name
    const contentListingLookup = {
      [contentListingKey(website.name, contentType, 0)]: {
        ...response,
        results: response.results.map(item => item.uuid)
      }
    }
    const details = {}
    for (const item of contentListingItems) {
      details[item.uuid] = item
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
        body:   response,
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
          websiteDetails:        websitesLookup,
          websiteContentListing: contentListingLookup,
          websiteContentDetails: details
        },
        queries: {}
      }
    )
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("should render a link to itself and to the add content page", async () => {
    const params = { name: website.name, contenttype: contentType }
    mockUseRouteMatch.mockImplementation(() => ({
      params
    }))
    const { wrapper } = await render()
    expect(
      wrapper
        .find("NavLink")
        .at(0)
        .prop("to")
    ).toBe(
      siteContentListingUrl
        .param({
          name: website.name,
          contentType
        })
        .toString()
    )
    expect(
      wrapper
        .find("NavLink")
        .at(1)
        .prop("to")
    ).toBe(
      siteAddContentUrl
        .param({
          name: website.name,
          contentType
        })
        .toString()
    )
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
    expect(wrapper.find("SiteEditContent").exists()).toBe(false)

    let idx = 0
    for (const item of contentListingItems) {
      const li = wrapper.find("li").at(idx)
      expect(li.text()).toContain(item.title)

      const link = li.find("a")
      expect(link.text()).toBe("Edit")
      act(() => {
        // @ts-ignore
        link.prop("onClick")({ preventDefault: helper.sandbox.stub() })
      })
      wrapper.update()
      const component = wrapper.find("SiteEditContent")
      expect(component.prop("uuid")).toBe(item.uuid)
      expect(component.prop("visibility")).toBe(true)

      act(() => {
        // @ts-ignore
        component.prop("toggleVisibility")()
      })
      wrapper.update()
      expect(wrapper.find("SiteEditContent").prop("visibility")).toBe(false)

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
        response.next = hasNextLink ? "next" : null
        response.previous = hasPrevLink ? "prev" : null
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
            body:   response,
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
