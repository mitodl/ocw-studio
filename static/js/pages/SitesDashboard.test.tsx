import React from "react"
import { screen, waitFor, fireEvent } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import SitesDashboard from "./SitesDashboard"

import { newSiteUrl, siteApiListingUrl, siteDetailUrl } from "../lib/urls"
import { WebsiteListingResponse } from "../query-configs/websites"
import { makeWebsites } from "../util/factories/websites"
import { IntegrationTestHelper } from "../testing_utils"

import { Website } from "../types/websites"
import * as searchHooks from "../hooks/search"
import { render } from "@testing-library/react"
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
    helper.patchInitialReduxState({
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
    })
  })

  test("lists a page", async () => {
    helper.render(<SitesDashboard />)
    for (const website of websites) {
      const link = screen.getByRole("link", { name: website.title })
      expect(link).toHaveAttribute(
        "href",
        siteDetailUrl.param({ name: website.name }).toString(),
      )
      expect(screen.getByText(website.short_id)).toBeInTheDocument()
    }
  })

  test("lets the user filter the sites", async () => {
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
    const [, { history }] = helper.render(<SitesDashboard />)
    const filterInput = screen.getByPlaceholderText(/search/i)

    await userEvent.clear(filterInput)
    await userEvent.type(filterInput, "my-search-string")
    await waitFor(
      () => {
        expect(history.location.search).toBe("?q=my-search-string")
      },
      { timeout: 1000 },
    )
  })

  test("should issue a request based on the 'q' param", async () => {
    const searchHelper = new IntegrationTestHelper("/?q=searchfilter")
    searchHelper.mockGetRequest(
      siteApiListingUrl
        .param({ offset: 0 })
        .query({ search: "searchfilter" })
        .toString(),
      response,
    )
    searchHelper.patchInitialReduxState({
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
    })
    searchHelper.render(<SitesDashboard />)
    await waitFor(() => {
      expect(searchHelper.handleRequest).toHaveBeenCalledWith(
        siteApiListingUrl
          .param({ offset: 0 })
          .query({ search: "searchfilter" })
          .toString(),
        "GET",
        { body: undefined, credentials: undefined, headers: undefined },
      )
    })
  })

  test("sets the page title", async () => {
    helper.render(<SitesDashboard />)
    expect(document.title).toBe("OCW Studio | Sites")
  })

  test("has an add link to the new site page", async () => {
    helper.render(<SitesDashboard />)
    const addLink = screen.getByRole("link", { name: /add/i })
    expect(addLink).toHaveAttribute("href", newSiteUrl.toString())
  })

  it("paginates the site results", async () => {
    response.count = 250
    const startingOffset = 70
    const paginationHelper = new IntegrationTestHelper(
      `/path/to/page?offset=${startingOffset}`,
    )
    paginationHelper.mockGetRequest(
      siteApiListingUrl.query({ offset: startingOffset }).toString(),
      response,
    )
    paginationHelper.patchInitialReduxState({
      entities: {
        websitesListing: {
          [String(startingOffset)]: {
            ...response,
            results: websites.map((site) => site.name),
          },
        },
        websiteDetails: websitesLookup,
      },
      queries: {},
    })

    const usePagination = jest.spyOn(searchHooks, "usePagination")
    const [{ container }] = paginationHelper.render(<SitesDashboard />)
    await waitFor(() => {
      expect(usePagination).toHaveBeenCalled()
    })
    const { next, previous } = usePagination.mock.results[0].value
    const nextLink = container.querySelector("a.next")
    const previousLink = container.querySelector("a.previous")
    expect(nextLink).toHaveAttribute(
      "href",
      `${next.pathname}?${next.search.replace("?", "")}`,
    )
    expect(previousLink).toHaveAttribute(
      "href",
      `${previous.pathname}?${previous.search.replace("?", "")}`,
    )
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

    const neverPublishedSite = {
        ...testWebsites[0],
        name: "never-published-site",
        uuid: "test-uuid-1",
        publish_date: null,
        draft_publish_date: null,
        live_publish_status: null,
        unpublished: false,
      },
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
      publishedSite = {
        ...testWebsites[3],
        name: "published-site",
        uuid: "test-uuid-4",
        publish_date: "2023-01-01T12:00:00Z",
        live_publish_status: PublishStatus.Success,
        unpublished: false,
        updated_on: "2023-01-15T12:30:45Z",
      },
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

    testHelper.patchInitialReduxState({
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
    })

    testHelper.render(<SitesDashboard />)

    expect(screen.getAllByText("Never Staged").length).toBeGreaterThan(0)
    expect(screen.getByText("Unpublished")).toBeInTheDocument()
    expect(screen.getByText("Draft")).toBeInTheDocument()
    expect(screen.getByText("Published")).toBeInTheDocument()
  })
})
