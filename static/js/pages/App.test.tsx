import React from "react"
import { screen, waitFor } from "@testing-library/react"

import App from "./App"
import { IntegrationTestHelper } from "../testing_utils"
import { makeWebsiteDetail } from "../util/factories/websites"
import { siteApiDetailUrl, sitesBaseUrl } from "../lib/urls"

import { Website } from "../types/websites"

describe("App", () => {
  let helper: IntegrationTestHelper,
    website: Website,
    siteDetailApiUrl: string,
    siteDetailUrl: string

  beforeEach(() => {
    helper = new IntegrationTestHelper()

    website = makeWebsiteDetail()
    siteDetailApiUrl = siteApiDetailUrl.param({ name: website.name }).toString()
    siteDetailUrl = `${sitesBaseUrl.toString()}${website.name}`
    helper.mockGetRequest(siteDetailApiUrl, website)
  })

  it("should render", async () => {
    helper.render(<App />)

    await waitFor(() => {
      expect(document.querySelector(".app")).toBeInTheDocument()
    })
  })

  it("should render 404 when no match", async () => {
    helper = new IntegrationTestHelper("/nonsense")
    helper.render(<App />)

    await screen.findByText(/that's a 404/i)
  })

  it("should render the site header", async () => {
    helper.render(<App />)

    await waitFor(() => {
      expect(document.querySelector("header")).toBeInTheDocument()
    })
  })

  it("should not make a request for website detail", async () => {
    helper.render(<App />)

    await waitFor(() => {
      expect(document.querySelector(".app")).toBeInTheDocument()
    })

    expect(helper.handleRequest).not.toHaveBeenCalledWith(
      siteDetailApiUrl,
      "GET",
      expect.anything(),
    )
  })

  describe("when on a website detail URL", () => {
    it("should load website from the API and render the SitePage component", async () => {
      helper = new IntegrationTestHelper(siteDetailUrl)
      helper.mockGetRequest(siteDetailApiUrl, website)

      helper.render(<App />)

      await waitFor(() => {
        expect(helper.handleRequest).toHaveBeenCalledWith(
          siteDetailApiUrl,
          "GET",
          expect.anything(),
        )
      })

      await screen.findByText(website.title)
    })

    it("should show a 404 if the website doesn't come back", async () => {
      helper = new IntegrationTestHelper(siteDetailUrl)
      helper.mockGetRequest(siteDetailApiUrl, {}, 404)

      helper.render(<App />)

      await screen.findByText(/that's a 404/i)

      const backLink = screen.getByRole("link", { name: /site index/i })
      expect(backLink).toHaveAttribute("href", sitesBaseUrl.toString())
    })
  })
})
