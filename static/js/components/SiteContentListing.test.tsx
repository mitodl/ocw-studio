const mockUseRouteMatch = jest.fn()

import { act } from "react-dom/test-utils"

import SiteContentListing from "./SiteContentListing"

import { siteAddContentUrl, siteContentListingUrl } from "../lib/urls"
import { contentListingKey } from "../query-configs/websites"
import IntegrationTestHelper, {
  TestRenderer
} from "../util/integration_test_helper"
import {
  makeWebsiteContentListItem,
  makeWebsiteDetail
} from "../util/factories/websites"

import { Website, WebsiteContentListItem } from "../types/websites"

jest.mock("react-router-dom", () => ({
  // @ts-ignore
  ...jest.requireActual("react-router-dom"),
  useRouteMatch: mockUseRouteMatch
}))

// ckeditor is not working properly in tests, but we don't need to test it here so just mock it away
jest.mock("./MarkdownEditor", () => "div")

describe("SiteContentListing", () => {
  let helper: IntegrationTestHelper,
    render: TestRenderer,
    website: Website,
    contentType: string,
    contentListingItems: WebsiteContentListItem[]

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    website = makeWebsiteDetail()
    const websitesLookup = { [website.name]: website }
    contentListingItems = [
      makeWebsiteContentListItem(),
      makeWebsiteContentListItem()
    ]
    // @ts-ignore
    contentType = website.starter?.config?.collections[0].name
    const contentListingLookup = {
      [contentListingKey(website.name, contentType)]: contentListingItems
    }
    helper.handleRequestStub
      .withArgs(
        `/api/websites/${website.name}/content/?type=${contentType}`,
        "GET"
      )
      .returns({
        body:   contentListingItems,
        status: 200
      })

    render = helper.configureRenderer(
      SiteContentListing,
      {},
      {
        entities: {
          websiteDetails:        websitesLookup,
          websiteContentListing: contentListingLookup
        },
        queries: {}
      }
    )
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("should render a link to itself and to the add content page", async () => {
    const params = { name: website.name, configname: contentType }
    mockUseRouteMatch.mockImplementation(() => ({
      params
    }))
    const { wrapper } = await render()
    expect(
      wrapper
        .find("NavLink")
        .at(0)
        .prop("to")
    ).toBe(siteContentListingUrl(params.name, params.configname))
    expect(
      wrapper
        .find("NavLink")
        .at(1)
        .prop("to")
    ).toBe(siteAddContentUrl(params.name, params.configname))
  })

  it("should show each content item with edit links", async () => {
    const params = { name: website.name, configname: contentType }
    mockUseRouteMatch.mockImplementation(() => ({
      params
    }))
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
})
