import SitesDashboard from "./SitesDashboard"

import { newSiteUrl, siteApiListingUrl, siteDetailUrl } from "../lib/urls"
import { WebsiteListingResponse } from "../query-configs/websites"
import { wait } from "../test_util"
import { makeWebsites } from "../util/factories/websites"
import IntegrationTestHelper, {
  TestRenderer,
} from "../util/integration_test_helper_old"

import { Website } from "../types/websites"
import PaginationControls from "../components/PaginationControls"
import * as searchHooks from "../hooks/search"
import React from "react"
import { render, fireEvent } from "@testing-library/react"
import { StatusWithDateHover, formatDateTime } from "./SitesDashboard"
import { PublishStatus } from "../constants"

jest.mock("../hooks/search", () => {
  return {
    __esModule: true,
    ...jest.requireActual("../hooks/search"),
  }
})

describe("SitesDashboard", () => {
  let helper: IntegrationTestHelper,
    response: WebsiteListingResponse,
    render: TestRenderer,
    websites: Website[],
    websitesLookup: Record<string, Website>

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    websites = makeWebsites()
    websitesLookup = {}
    for (const site of websites) {
      websitesLookup[site.name] = site
    }
    response = {
      results: websites,
      next: "https://example.com",
      previous: null,
      count: 10,
    }
    helper.mockGetRequest(
      siteApiListingUrl.param({ offset: 0 }).toString(),
      response,
    )

    render = helper.configureRenderer(
      SitesDashboard,
      {},
      {
        entities: {
          websitesListing: {
            ["0"]: {
              ...response,
              results: websites.map((site) => site.name),
            },
          },
          websiteDetails: websitesLookup,
        },
        queries: {},
      },
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
        siteDetailUrl.param({ name: website.name }).toString(),
      )
      expect(li.find("Link").text()).toBe(website.title)
      expect(li.prop("subtitle")).toBe(website.short_id)
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
        results: [],
        next: "null",
        previous: null,
        count: 0,
      },
    )

    const event = {
      // eslint-disable-next-line @typescript-eslint/no-empty-function
      preventDefault() {},
      target: { value: "my-search-string" },
    } as React.ChangeEvent<HTMLInputElement>
    filterInput.simulate("change", event)
    await wait(800)
    expect(helper.browserHistory.location.search).toBe("?q=my-search-string")
  })

  test("should issue a request based on the 'q' param", async () => {
    helper.browserHistory.replace({
      pathname: "/",
      search: "q=searchfilter",
    })
    helper.mockGetRequest(
      siteApiListingUrl
        .param({ offset: 0 })
        .query({ search: "searchfilter" })
        .toString(),
      response,
    )
    await render()
    expect(helper.handleRequestStub.args).toStrictEqual([
      [
        siteApiListingUrl
          .param({ offset: 0 })
          .query({ search: "searchfilter" })
          .toString(),
        "GET",
        { body: undefined, credentials: undefined, headers: undefined },
      ],
    ])
  })

  test("sets the page title", async () => {
    const { wrapper } = await render()
    expect(wrapper.find("DocumentTitle").prop("title")).toBe(
      "OCW Studio | Sites",
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
      response,
    )
    helper.browserHistory.replace({
      pathname: "/path/to/page",
      search: `offset=${startingOffset}`,
    })

    const usePagination = jest.spyOn(searchHooks, "usePagination")
    const { wrapper } = await render()
    const paginationControls = wrapper.find(PaginationControls)
    expect(usePagination).toHaveBeenCalledTimes(2) // once on initial render, once after api call resolves
    const { next, previous } = usePagination.mock.results[1].value
    expect(paginationControls.prop("next")).toBe(next)
    expect(paginationControls.prop("previous")).toBe(previous)
  })
})

describe("StatusWithDateHover component", () => {
  it("displays status text by default", () => {
    const { getByText } = render(
      <StatusWithDateHover
        statusText="Published"
        dateTime="2023-01-15T12:30:45Z"
        className="text-success"
      />,
    )

    expect(getByText("Published")).toBeInTheDocument()
  })

  it("shows formatted date on hover", () => {
    const { getByText, container } = render(
      <StatusWithDateHover
        statusText="Published"
        dateTime="2023-01-15T12:30:45Z"
        className="text-success"
      />,
    )

    const element = container.firstChild as HTMLElement
    fireEvent.mouseEnter(element)

    expect(getByText(/Published on Jan 15, 2023/)).toBeInTheDocument()
  })

  it("shows 'Staged on' for draft sites on hover", () => {
    const { getByText, container } = render(
      <StatusWithDateHover
        statusText="Draft"
        hoverText="Staged"
        dateTime="2023-01-15T12:30:45Z"
        className="text-info"
      />,
    )

    const element = container.firstChild as HTMLElement
    fireEvent.mouseEnter(element)

    expect(getByText(/Staged on Jan 15, 2023/)).toBeInTheDocument()
  })

  it("reverts to status text when mouse leaves", () => {
    const { getByText, container } = render(
      <StatusWithDateHover
        statusText="Published"
        dateTime="2023-01-15T12:30:45Z"
        className="text-success"
      />,
    )

    const element = container.firstChild as HTMLElement

    // Hover
    fireEvent.mouseEnter(element)
    expect(getByText(/Published on Jan 15, 2023/)).toBeInTheDocument()

    // Un-hover
    fireEvent.mouseLeave(element)
    expect(getByText("Published")).toBeInTheDocument()
  })

  it("applies the provided className", () => {
    const { container } = render(
      <StatusWithDateHover
        statusText="Published"
        dateTime="2023-01-15T12:30:45Z"
        className="text-success"
      />,
    )

    expect(container.firstChild).toHaveClass("text-success")
  })
})

describe("formatDateTime function", () => {
  it("formats date strings", () => {
    const result = formatDateTime("2023-01-15T12:30:45Z")

    expect(result).toContain("2023")
    expect(result).toContain("Jan")
    expect(result).toContain("15")
  })
})

describe("Site status indicators", () => {
  it("shows status for different site states", async () => {
    const testHelper = new IntegrationTestHelper()
    const testWebsites = makeWebsites(5)

    // Never published site - no publish dates or statuses
    const neverPublishedSite = {
        ...testWebsites[0],
        name: "never-published-site",
        uuid: "test-uuid-1",
        publish_date: null,
        draft_publish_date: null,
        live_publish_status: null,
        unpublished: false,
      },
      // Unpublished site - has publish_date but marked as unpublished
      unpublishedSite = {
        ...testWebsites[1],
        name: "unpublished-site",
        uuid: "test-uuid-2",
        publish_date: "2023-01-01T12:00:00Z",
        unpublished: true,
        unpublish_status: PublishStatus.Success,
        unpublish_status_updated_on: "2023-01-15T12:30:45Z",
        updated_on: "2023-01-15T12:30:45Z",
      },
      // Draft site - has draft_publish_status and draft_publish_date
      // but no publish_date and unpublished is false
      draftSite = {
        ...testWebsites[2],
        name: "draft-site",
        uuid: "test-uuid-3",
        draft_publish_date: "2023-01-15T12:30:45Z",
        draft_publish_status: PublishStatus.Success,
        publish_date: null,
        live_publish_status: null,
        unpublished: false,
        updated_on: "2023-01-15T12:30:45Z",
      },
      // Published site - has publish_date and live_publish_status
      publishedSite = {
        ...testWebsites[3],
        name: "published-site",
        uuid: "test-uuid-4",
        publish_date: "2023-01-01T12:00:00Z",
        live_publish_status: PublishStatus.Success,
        unpublished: false,
        updated_on: "2023-01-15T12:30:45Z",
      },
      // Failed site - has live_publish_status marked as errored
      failedSite = {
        ...testWebsites[4],
        name: "failed-site",
        uuid: "test-uuid-5",
        publish_date: "2023-01-01T12:00:00Z",
        live_publish_status: PublishStatus.Errored,
        unpublished: false,
        updated_on: "2023-01-15T12:30:45Z",
      }

    const statusSites = [
      neverPublishedSite,
      unpublishedSite,
      draftSite,
      publishedSite,
      failedSite,
    ]
    const testResponse = {
      results: statusSites,
      next: "https://example.com",
      previous: null,
      count: statusSites.length,
    }

    testHelper.mockGetRequest(
      siteApiListingUrl.param({ offset: 0 }).toString(),
      testResponse,
    )

    const websitesLookup: Record<string, Website> = {}
    for (const site of statusSites) {
      websitesLookup[site.name] = site
    }

    const testRender = testHelper.configureRenderer(
      SitesDashboard,
      {},
      {
        entities: {
          websitesListing: {
            ["0"]: {
              ...testResponse,
              results: statusSites.map((site) => site.name),
            },
          },
          websiteDetails: websitesLookup,
        },
        queries: {},
      },
    )

    const { wrapper } = await testRender()

    // Check for status text
    expect(wrapper.text()).toContain("Never Staged")
    expect(wrapper.text()).toContain("Unpublished")
    expect(wrapper.text()).toContain("Draft")
    expect(wrapper.text()).toContain("Published")

    // Cleanup
    testHelper.cleanup()
  })
})
