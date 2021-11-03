import * as React from "react"

import IntegrationTestHelper, {
  TestRenderer
} from "../util/integration_test_helper"
import { makeWebsiteDetail } from "../util/factories/websites"
import { siteApiCollaboratorsUrl, siteDetailUrl } from "../lib/urls"
import SitePage from "./SitePage"
import WebsiteContext from "../context/Website"

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

  it("renders a loading message", async () => {
    const { wrapper } = await render({ isLoading: true })
    expect(wrapper.text()).toEqual("Loading...")
  })

  it("renders the sidebar", async () => {
    const { wrapper } = await render()
    expect(wrapper.find("SiteSidebar").prop("website")).toBe(website)
  })

  //
  ;[
    [`/sites/${siteName}/collaborators/`, "SiteCollaboratorList"],
    [`/sites/${siteName}/type/some-type/`, "SiteContentListing"]
  ].forEach(([url, expComponent]) => {
    it(`renders a ${expComponent} component when the browser URL matches`, async () => {
      helper.browserHistory.push(url)
      const { wrapper } = await render()
      expect(wrapper.find(expComponent).exists()).toBe(true)
    })
  })
})
