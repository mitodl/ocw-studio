const mockUseRouteMatch = jest.fn()

import { fromPairs } from "lodash"

import SiteContentListing from "./SiteContentListing"

import IntegrationTestHelper, {
  TestRenderer
} from "../util/integration_test_helper"
import { makeWebsiteDetails } from "../util/factories/websites"
import { siteContentListingUrl } from "../lib/urls"

import { Website } from "../types/websites"

jest.mock("react-router-dom", () => ({
  // @ts-ignore
  ...jest.requireActual("react-router-dom"),
  useRouteMatch: mockUseRouteMatch
}))

describe("SiteContentListing", () => {
  let helper: IntegrationTestHelper, render: TestRenderer, websites: Website[]

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    websites = makeWebsiteDetails()
    const websitesLookup = fromPairs(
      websites.map(website => [website.name, website])
    )
    render = helper.configureRenderer(
      SiteContentListing,
      {},
      {
        entities: {
          websiteDetails: websitesLookup
        },
        queries: {}
      }
    )
  })

  it("should render a simple link", async () => {
    const params = { name: websites[0].name, configname: "page" }
    mockUseRouteMatch.mockImplementation(() => ({
      params
    }))
    const { wrapper } = await render()
    expect(wrapper.find("NavLink").prop("to")).toBe(
      siteContentListingUrl(params.name, params.configname)
    )
  })
})
