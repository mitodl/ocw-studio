import SitesDashboard, { siteDescription } from "./SitesDashboard"

import { WEBSITES_PAGE_SIZE } from "../constants"
import {
  newSiteUrl,
  siteApiListingUrl,
  siteDetailUrl,
  sitesBaseUrl
} from "../lib/urls"
import { WebsiteListingResponse } from "../query-configs/websites"
import { isIf } from "../test_util"
import {
  makeWebsiteListing,
  makeWebsiteDetail
} from "../util/factories/websites"
import IntegrationTestHelper, {
  TestRenderer
} from "../util/integration_test_helper"

import { Website } from "../types/websites"

describe("SitesDashboard", () => {
  let helper: IntegrationTestHelper,
    response: WebsiteListingResponse,
    render: TestRenderer,
    websites: Website[],
    websitesLookup: Record<string, Website>

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    websites = makeWebsiteListing()
    websitesLookup = {}
    for (const site of websites) {
      websitesLookup[site.name] = site
    }
    response = {
      results:  websites,
      next:     "https://example.com",
      previous: null,
      count:    10
    }
    helper.mockGetRequest(
      siteApiListingUrl.param({ offset: 0 }).toString(),
      response
    )
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
            ["0"]: {
              ...response,
              results: websites.map(site => site.name)
            }
          },
          websiteDetails: websitesLookup
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
      expect(li.find("Link").prop("to")).toBe(
        siteDetailUrl.param({ name: website.name }).toString()
      )
      expect(li.find("Link").text()).toBe(website.title)
      expect(li.find(".site-description").text()).toBe(siteDescription(website))
      idx++
    }
  })

  it("has an add link to the new site page", async () => {
    const { wrapper } = await render()
    expect(wrapper.find(`Link.add-new`).prop("to")).toBe(newSiteUrl.toString())
  })

  //
  ;[true, false].forEach(hasPrevLink => {
    [true, false].forEach(hasNextLink => {
      it(`shows the right links when there ${isIf(
        hasPrevLink
      )} a previous link and ${isIf(hasNextLink)} a next link`, async () => {
        response.next = hasNextLink ? "next" : null
        response.previous = hasPrevLink ? "prev" : null
        const startingOffset = 20
        helper.mockGetRequest(
          siteApiListingUrl.query({ offset: startingOffset }).toString(),
          response
        )
        const { wrapper } = await render({
          location: {
            search: `offset=${startingOffset}`
          }
        })

        const prevWrapper = wrapper.find(".pagination Link.previous")
        expect(prevWrapper.exists()).toBe(hasPrevLink)
        if (hasPrevLink) {
          expect(prevWrapper.prop("to")).toBe(
            sitesBaseUrl
              .query({ offset: startingOffset - WEBSITES_PAGE_SIZE })
              .toString()
          )
        }

        const nextWrapper = wrapper.find(".pagination Link.next")
        expect(nextWrapper.exists()).toBe(hasNextLink)
        if (hasNextLink) {
          expect(nextWrapper.prop("to")).toBe(
            sitesBaseUrl
              .query({ offset: startingOffset + WEBSITES_PAGE_SIZE })
              .toString()
          )
        }
      })
    })
  })

  describe("siteDescription", () => {
    it("makes description text for a site with metadata", () => {
      const site = {
        ...makeWebsiteDetail(),
        metadata: null
      }
      expect(siteDescription(site)).toBe(null)
    })

    it("makes description text for a site without metadata", () => {
      const site = makeWebsiteDetail()
      expect(siteDescription(site)).toBe(
        `${site.metadata.course_numbers[0]} - ${site.metadata.term}`
      )
    })
  })
})
