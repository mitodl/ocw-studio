import SitesDashboard, { siteDescription } from "./SitesDashboard"

import { newSiteUrl, siteApiListingUrl, siteDetailUrl } from "../lib/urls"
import { WebsiteListingResponse } from "../query-configs/websites"
import { wait } from "../test_util"
import {
  makeWebsiteListing,
  makeWebsiteDetail
} from "../util/factories/websites"
import IntegrationTestHelper, {
  TestRenderer
} from "../util/integration_test_helper_old"

import { Website } from "../types/websites"
import PaginationControls from "../components/PaginationControls"
import * as searchHooks from "../hooks/search"

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

  test("lists a page", async () => {
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

  test("lets the user filter the sites", async () => {
    const { wrapper } = await render()
    const filterInput = wrapper.find(".site-search-input")
    helper.mockGetRequest(
      siteApiListingUrl
        .param({ offset: 0, search: "my-search-string" })
        .toString(),
      {
        results:  [],
        next:     "null",
        previous: null,
        count:    0
      }
    )

    const event = {
      // eslint-disable-next-line @typescript-eslint/no-empty-function
      preventDefault() {},
      target: { value: "my-search-string" }
    } as React.ChangeEvent<HTMLInputElement>
    filterInput.simulate("change", event)
    await wait(800)
    expect(helper.browserHistory.location.search).toBe("?q=my-search-string")
  })

  test("should issue a request based on the 'q' param", async () => {
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
    expect(helper.handleRequestStub.args).toStrictEqual([
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

  test("sets the page title", async () => {
    const { wrapper } = await render()
    expect(wrapper.find("DocumentTitle").prop("title")).toBe(
      "OCW Studio | Sites"
    )
  })

  test("has an add link to the new site page", async () => {
    const { wrapper } = await render()
    expect(wrapper.find(`Link.add-new`).prop("to")).toBe(newSiteUrl.toString())
  })

  it("paginates the site results", async () => {
    /**
     * SitesDashboard uses the same usePagination hook as RepeatableContentListing.
     * The hook is tested pretty thoroughly through its usage in that component.
     * Let's just assert that this component uses the hook and passes its results
     * to the pagination controls.
     */
    response.count = 250
    const startingOffset = 70
    helper.mockGetRequest(
      siteApiListingUrl.query({ offset: startingOffset }).toString(),
      response
    )
    helper.browserHistory.replace({
      pathname: "/path/to/page",
      search:   `offset=${startingOffset}`
    })

    const usePagination = jest.spyOn(searchHooks, "usePagination")
    const { wrapper } = await render()
    const paginationControls = wrapper.find(PaginationControls)
    expect(usePagination).toHaveBeenCalledTimes(2) // once on initial render, once after api call resolves
    const { next, previous } = usePagination.mock.results[1].value
    expect(paginationControls.prop("next")).toBe(next)
    expect(paginationControls.prop("previous")).toBe(previous)
  })

  test("makes description text for a site with metadata", () => {
    const site = {
      ...makeWebsiteDetail(),
      metadata: null
    }
    expect(siteDescription(site)).toBe(null)
  })

  test("makes description text for a site without metadata", () => {
    const site = makeWebsiteDetail()
    expect(siteDescription(site)).toBe(
      `${site.metadata.course_numbers[0]} - ${site.metadata.term}`
    )
  })
})
