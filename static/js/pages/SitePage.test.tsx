const mockUseRouteMatch = jest.fn()

import SitePage from "./SitePage"

import IntegrationTestHelper, {
  TestRenderer
} from "../util/integration_test_helper"
import { makeWebsiteDetail } from "../util/factories/websites"

import { siteApiDetailUrl } from "../lib/urls"

import { Website } from "../types/websites"

jest.mock("react-router-dom", () => ({
  // @ts-ignore
  ...jest.requireActual("react-router-dom"),
  useRouteMatch: mockUseRouteMatch
}))

describe("SitePage", () => {
  let helper: IntegrationTestHelper, render: TestRenderer, website: Website

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    website = makeWebsiteDetail()
    render = helper.configureRenderer(
      SitePage,
      {},
      {
        entities: {
          websiteDetails: {}
        },
        queries: {}
      }
    )
    mockUseRouteMatch.mockImplementation(() => ({
      params: {
        name: website.name
      }
    }))
    helper.handleRequestStub
      .withArgs(
        siteApiDetailUrl.param({ name: website.name }).toString(),
        "GET"
      )
      .returns({
        body:   website,
        status: 200
      })
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("renders the sidebar", async () => {
    const { wrapper } = await render()
    expect(wrapper.find("SiteSidebar").prop("website")).toBe(website)
    expect(wrapper.find("h1.title").text()).toBe(website.title)
  })
})
