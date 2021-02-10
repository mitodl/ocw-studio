const mockUseRouteMatch = jest.fn()

import SitePage from "./SitePage"

import IntegrationTestHelper from "../util/integration_test_helper"
import { makeWebsite } from "../util/factories/websites"

import { Website } from "../types/websites"

jest.mock("react-router-dom", () => ({
  // @ts-ignore
  ...jest.requireActual("react-router-dom"),
  useRouteMatch: mockUseRouteMatch
}))

describe("SitePage", () => {
  let helper: IntegrationTestHelper,
    render: ReturnType<IntegrationTestHelper["configureRenderer"]>,
    website: Website

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    website = makeWebsite()
    render = helper.configureRenderer(
      SitePage,
      {},
      {
        entities: {
          websites: {}
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
      .withArgs(`/api/websites/${website.name}/`, "GET")
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
  })

  it("renders the title", async () => {
    const { wrapper } = await render()
    expect(wrapper.find(".site-page-header").text()).toBe(website.title)
  })
})
