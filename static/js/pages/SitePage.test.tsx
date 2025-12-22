import React from "react"
import { screen, waitFor } from "@testing-library/react"

import { IntegrationTestHelper } from "../testing_utils"
import { makeWebsiteDetail } from "../util/factories/websites"
import {
  siteApiCollaboratorsUrl,
  siteDetailUrl,
  siteCollaboratorsUrl,
  siteContentListingUrl,
} from "../lib/urls"
import SitePage from "./SitePage"
import WebsiteContext from "../context/Website"

import { Website } from "../types/websites"

describe("SitePage", () => {
  const siteName = "fakeSiteName"
  let helper: IntegrationTestHelper, website: Website

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    website = {
      ...makeWebsiteDetail(),
      name: siteName,
    }
    helper.mockGetRequest(
      siteApiCollaboratorsUrl
        .param({ name: website.name })
        .query({ offset: 0 })
        .toString(),
      { results: [], count: 0, next: null, previous: null },
    )
  })

  const renderSitePage = (props: { isLoading?: boolean } = {}) => {
    return helper.render(
      <WebsiteContext.Provider value={website}>
        <SitePage isLoading={props.isLoading ?? false} />
      </WebsiteContext.Provider>,
    )
  }

  it("sets the document title", async () => {
    helper = new IntegrationTestHelper(
      siteDetailUrl.param("name", website.name).toString(),
    )
    helper.mockGetRequest(
      siteApiCollaboratorsUrl
        .param({ name: website.name })
        .query({ offset: 0 })
        .toString(),
      { results: [], count: 0, next: null, previous: null },
    )

    renderSitePage()

    await waitFor(() => {
      expect(document.title).toContain(website.title)
    })
  })

  it.each([true, false])(
    "renders a loading spinner when isLoading=%s",
    async (isLoading) => {
      renderSitePage({ isLoading })

      if (isLoading) {
        expect(screen.getByRole("status")).toBeInTheDocument()
      } else {
        expect(screen.queryByRole("status")).not.toBeInTheDocument()
      }
    },
  )

  it("keeps old content rendered while loading", async () => {
    renderSitePage({ isLoading: true })

    expect(document.querySelector(".site-page")).toBeInTheDocument()
  })

  it("renders the sidebar", async () => {
    renderSitePage()

    await waitFor(() => {
      expect(document.querySelector(".sidebar")).toBeInTheDocument()
    })
  })

  it("renders a SiteCollaboratorList component when the browser URL matches", async () => {
    helper = new IntegrationTestHelper(
      siteCollaboratorsUrl.param({ name: siteName }).toString(),
    )
    helper.mockGetRequest(
      siteApiCollaboratorsUrl
        .param({ name: website.name })
        .query({ offset: 0 })
        .toString(),
      { results: [], count: 0, next: null, previous: null },
    )

    renderSitePage()

    await screen.findByRole("heading", { name: /collaborators/i })
  })

  it("renders a SiteContentListing component when the browser URL matches", async () => {
    helper = new IntegrationTestHelper(
      siteContentListingUrl
        .param({ name: siteName, contentType: "some-type" })
        .toString(),
    )
    helper.mockGetRequest(
      siteApiCollaboratorsUrl
        .param({ name: website.name })
        .query({ offset: 0 })
        .toString(),
      { results: [], count: 0, next: null, previous: null },
    )

    renderSitePage()

    await waitFor(() => {
      expect(document.querySelector(".site-page")).toBeInTheDocument()
    })
  })
})
