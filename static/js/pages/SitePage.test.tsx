import React from "react"
import { Route } from "react-router-dom"

import IntegrationTestHelper, {
  TestRenderer
} from "../util/integration_test_helper"
import { makeWebsiteDetail } from "../util/factories/websites"
import { siteApiCollaboratorsUrl, siteDetailUrl } from "../lib/urls"
import SitePage from "./SitePage"
import WebsiteContext from "../context/Website"
import Spinner from "../components/util/Spinner"
import SiteCollaboratorList from "../components/SiteCollaboratorList"
import SiteContentListing from "../components/SiteContentListing"

import { Website } from "../types/websites"

describe("SitePage", () => {
  const siteName = "fakeSiteName"
  let helper: IntegrationTestHelper, render: TestRenderer, website: Website

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    website = {
      ...makeWebsiteDetail(),
      name: siteName
    }
    helper.mockGetRequest(
      siteApiCollaboratorsUrl.param({ name: website.name }).toString(),
      { results: [] }
    )
    render = helper.configureRenderer(
      (props = {}) => (
        <WebsiteContext.Provider value={website}>
          <SitePage {...props} />
        </WebsiteContext.Provider>
      ),
      { siteName: website.name }
    )
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("sets the document title", async () => {
    helper.browserHistory.push(
      siteDetailUrl.param("name", website.name).toString()
    )
    const { wrapper } = await render()
    expect(wrapper.find("DocumentTitle").prop("title")).toBe(
      `OCW Studio | ${website.title}`
    )
  })

  it.each([true, false])(
    "renders a loading spinner when isLoading=%s",
    async isLoading => {
      const { wrapper } = await render({ isLoading })

      const spinner = wrapper.find(Spinner)
      expect(spinner.exists()).toBe(isLoading)
    }
  )

  it("keeps old content rendered while loading", async () => {
    const { wrapper } = await render({ isLoading: true })
    const routes = wrapper.find(Route)
    expect(routes.exists()).toBe(true)
  })

  it("renders the sidebar", async () => {
    const { wrapper } = await render()
    expect(wrapper.find("SiteSidebar").prop("website")).toBe(website)
  })

  it.each([
    {
      url:       `/sites/${siteName}/collaborators/`,
      component: SiteCollaboratorList
    },
    {
      url:       `/sites/${siteName}/type/some-type/`,
      component: SiteContentListing
    }
  ])(
    `renders a $component.name component when the browser URL matches`,
    async ({ url, component }) => {
      helper.browserHistory.push(url)
      const { wrapper } = await render()
      expect(wrapper.find(component).exists()).toBe(true)
    }
  )
})
