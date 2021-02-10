const mockUseRouteMatch = jest.fn()

import { fromPairs } from "lodash"

import SiteComponent from "./SiteComponent"

import IntegrationTestHelper from "../util/integration_test_helper"
import { makeWebsites } from "../util/factories/websites"
import { siteComponentUrl } from "../lib/urls"

import { Website } from "../types/websites"

jest.mock("react-router-dom", () => ({
  // @ts-ignore
  ...jest.requireActual("react-router-dom"),
  useRouteMatch: mockUseRouteMatch
}))

describe("SiteComponent", () => {
  let helper: IntegrationTestHelper,
    render: ReturnType<IntegrationTestHelper["configureRenderer"]>,
    websites: Website[]

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    websites = makeWebsites()
    const websitesLookup = fromPairs(
      websites.map(website => [website.name, website])
    )
    render = helper.configureRenderer(
      SiteComponent,
      {},
      {
        entities: {
          websites: websitesLookup
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
      siteComponentUrl(params.name, params.configname)
    )
  })
})
