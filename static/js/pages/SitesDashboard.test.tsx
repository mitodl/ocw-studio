import SitesDashboard, { siteDescription } from "./SitesDashboard"

import { WEBSITES_PAGE_SIZE } from "../constants"
import {
  newSiteUrl,
  siteApiListingUrl,
  siteDetailUrl,
  sitesBaseUrl
} from "../lib/urls"
import { WebsiteListingResponse } from "../query-configs/websites"
import { isIf, wait } from "../test_util"
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
      {},
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
      const li = wrapper.find("StudioListItem").at(idx)
      expect(li.prop("to")).toBe(
        siteDetailUrl.param({ name: website.name }).toString()
      )
      expect(li.find("Link").text()).toBe(website.title)
      expect(li.prop("subtitle")).toBe(siteDescription(website))
      idx++
    }
  })

  it("lets the user filter the sites", async () => {
    const { wrapper } = await render()
    const filterInput = wrapper.find(".site-search-input")
    const event = {
      // eslint-disable-next-line @typescript-eslint/no-empty-function
      preventDefault() {},
      target: { value: "my-search-string" }
    } as React.ChangeEvent<HTMLInputElement>
    filterInput.simulate("change", event)
    await wait(800)
    expect(helper.browserHistory.location.search).toBe(
      "offset=0&q=my-search-string"
    )
  })

  it("should issue a request based on the 'q' param", async () => {
    helper.browserHistory.replace({
      pathname: "/",
      search:   "q=searchfilter"
    })
    helper.mockGetRequest(
      siteApiListingUrl
        .param({ offset: 0 })
        .query({ search: "searchfilter" })
        .toString(),
      response
    )
    await render()
    expect(helper.handleRequestStub.mock.calls[0]).toStrictEqual([
      [
        siteApiListingUrl
          .param({ offset: 0 })
          .query({ search: "searchfilter" })
          .toString(),
        "GET",
        { body: undefined, credentials: undefined, headers: undefined }
      ]
    ])
  })

  it("sets the page title", async () => {
    const { wrapper } = await render()
    expect(wrapper.find("DocumentTitle").prop("title")).toBe(
      "OCW Studio | Sites"
    )
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
        helper.browserHistory.replace({
          pathname: "/path/to/page",
          search:   `offset=${startingOffset}`
        })
        const { wrapper } = await render()

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
