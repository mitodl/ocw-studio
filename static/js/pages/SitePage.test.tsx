const mockUseRouteMatch = jest.fn()

import { act } from "react-dom/test-utils"

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

    helper.mockGetRequest(
      siteApiDetailUrl.param({ name: website.name }).toString(),
      website
    )
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("renders the sidebar", async () => {
    const { wrapper } = await render()
    expect(wrapper.find("SiteSidebar").prop("website")).toBe(website)
    expect(wrapper.find("h1.title").text()).toBe(website.title)
  })

  it("toggles the publish drawer", async () => {
    const { wrapper } = await render()
    expect(wrapper.find("PublishDrawer").prop("visibility")).toBeFalsy()
    act(() => {
      // @ts-ignore
      wrapper.find("PublishDrawer").prop("toggleVisibility")()
    })
    wrapper.update()
    expect(wrapper.find("PublishDrawer").prop("visibility")).toBeTruthy()
    act(() => {
      // @ts-ignore
      wrapper.find("PublishDrawer").prop("toggleVisibility")()
    })
    wrapper.update()
    expect(wrapper.find("PublishDrawer").prop("visibility")).toBeFalsy()
  })
})
