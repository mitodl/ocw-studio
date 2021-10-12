import sinon from "sinon"

import App from "./App"
import IntegrationTestHelper, {
  TestRenderer
} from "../util/integration_test_helper"
import { makeWebsiteDetail } from "../util/factories/websites"
import { siteApiDetailUrl, sitesBaseUrl } from "../lib/urls"

import { Website } from "../types/websites"

describe("App", () => {
  let helper: IntegrationTestHelper,
    render: TestRenderer,
    website: Website,
    siteDetailApiUrl: string

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    render = helper.configureRenderer(App)

    website = makeWebsiteDetail()
    siteDetailApiUrl = siteApiDetailUrl.param({ name: website.name }).toString()
    helper.mockGetRequest(siteDetailApiUrl, website)
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("should render", async () => {
    const { wrapper } = await render()
    expect(wrapper.find("App").exists()).toBeTruthy()
  })

  it("should render the site header", async () => {
    const { wrapper } = await render()
    const app = wrapper.find("App")
    const header = app.find("Header")
    expect(header.exists()).toBeTruthy()
  })

  it("should not make a request for website detail", async () => {
    await render()
    sinon.assert.notCalled(helper.handleRequestStub)
  })

  describe("when on a website detail URL", () => {
    it("should load website from the API and render the SitePage component", async () => {
      const siteDetailUrl = `${sitesBaseUrl.toString()}${website.name}`
      helper.browserHistory.push(siteDetailUrl)
      const { wrapper } = await render()
      sinon.assert.calledWith(helper.handleRequestStub, siteDetailApiUrl, "GET")
      const sitePageComponent = wrapper.find("SitePage")
      expect(sitePageComponent.exists()).toBe(true)
    })
  })
})
