const mockUseRouteMatch = jest.fn()

import SitesDashboard, { siteDescription } from "./SitesDashboard"

import { WEBSITES_PAGE_SIZE } from "../constants"
import {
  newSiteUrl,
  siteApiListingUrl,
  siteDetailUrl,
  siteListingUrl
} from "../lib/urls"
import { WebsiteListingResponse } from "../query-configs/websites"
import { isIf } from "../test_util"
import {
  makeWebsiteListing,
  makeWebsiteListingItem
} from "../util/factories/websites"
import IntegrationTestHelper, {
  TestRenderer
} from "../util/integration_test_helper"

import { Website } from "../types/websites"

jest.mock("react-router-dom", () => ({
  // @ts-ignore
  ...jest.requireActual("react-router-dom"),
  useRouteMatch: mockUseRouteMatch
}))

describe("SitesDashboard", () => {
  let helper: IntegrationTestHelper,
    response: WebsiteListingResponse,
    render: TestRenderer,
    websites: Website[]

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    websites = makeWebsiteListing()
    response = {
      results:  websites,
      next:     "https://example.com",
      previous: null,
      count:    10
    }
    helper.handleRequestStub.withArgs(siteApiListingUrl(0), "GET").returns({
      body:   response,
      status: 200
    })
    render = helper.configureRenderer(
      SitesDashboard,
      {
        location: {
          search: ""
        }
      },
      {
        entities: {
          websitesListing: {
            ["0"]: response
          }
        },
        queries: {}
      }
    )
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("lists a page", async () => {
    const { wrapper } = await render()
    let idx = 0
    for (const website of websites) {
      const li = wrapper
        .find("ul.listing")
        .find("li")
        .at(idx)
      expect(li.find("Link").prop("to")).toBe(siteDetailUrl(website.name))
      expect(li.find("Link").text()).toBe(website.title)
      expect(li.find(".site-description").text()).toBe(siteDescription(website))
      idx++
    }
  })

  it("has an add link to the new site page", async () => {
    const { wrapper } = await render()
    expect(wrapper.find(`Link.add-new`).prop("to")).toBe(newSiteUrl())
  })
  ;[true, false].forEach(hasPrevLink => {
    [true, false].forEach(hasNextLink => {
      it(`shows the right links when there ${isIf(
        hasPrevLink
      )} a previous link and ${isIf(
        hasNextLink
      )} has a next link`, async () => {
        response.next = hasNextLink ? "next" : null
        response.previous = hasPrevLink ? "prev" : null
        const startingOffset = 0
        const { wrapper } = await render({
          location: {
            search: `offset=${startingOffset}`
          }
        })
        console.log("wrapper", wrapper.debug())

        const prevWrapper = wrapper.find(".pagination Link.previous")
        expect(prevWrapper.exists()).toBe(hasPrevLink)
        if (hasPrevLink) {
          expect(prevWrapper.prop("to")).toBe(
            siteListingUrl(startingOffset - WEBSITES_PAGE_SIZE)
          )
        }

        const nextWrapper = wrapper.find(".pagination Link.next")
        expect(nextWrapper.exists()).toBe(hasNextLink)
        if (hasNextLink) {
          expect(nextWrapper.prop("to")).toBe(
            siteListingUrl(startingOffset + WEBSITES_PAGE_SIZE)
          )
        }
      })
    })
  })

  describe("siteDescription", () => {
    it("makes description text for a site with metadata", () => {
      const site = makeWebsiteListingItem()
      site.metadata = null
      expect(siteDescription(site)).toBe(null)
    })

    it("makes description text for a site without metadata", () => {
      const site = makeWebsiteListingItem()
      expect(siteDescription(site)).toBe(
        `${site.metadata.course_numbers[0]} - ${site.metadata.term}`
      )
    })
  })
})
