const mockUseRouteMatch = jest.fn()

import SitePage from "./SitePage"

import IntegrationTestHelper, {
  TestRenderer
} from "../util/integration_test_helper"
import { makeWebsiteDetail } from "../util/factories/websites"

import { WebsiteDetail } from "../types/websites"

jest.mock("react-router-dom", () => ({
  // @ts-ignore
  ...jest.requireActual("react-router-dom"),
  useRouteMatch: mockUseRouteMatch
}))

describe("SitePage", () => {
  let helper: IntegrationTestHelper,
    render: TestRenderer,
    website: WebsiteDetail

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
})
