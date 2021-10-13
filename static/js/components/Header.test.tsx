import { act } from "react-dom/test-utils"

import Header from "./Header"
import IntegrationTestHelper, {
  TestRenderer
} from "../util/integration_test_helper"
import { logoutUrl } from "../lib/urls"
import { makeWebsiteDetail } from "../util/factories/websites"
import { Website } from "../types/websites"

describe("Header", () => {
  let helper: IntegrationTestHelper, render: TestRenderer

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    render = helper.configureRenderer(Header)
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("includes the site logo", async () => {
    const { wrapper } = await render()
    expect(wrapper.find("img").prop("src")).toBe(
      "/static/images/ocw-studio-logo.png"
    )
  })

  it("shows the user's name and logout link for logged in users", async () => {
    const { wrapper } = await render()
    const links = wrapper.find(".links")
    expect(links.exists()).toBe(true)
    expect(links.find("span").text()).toBe("Jane Doe")
    const logoutLink = links.find("a")
    expect(logoutLink.text()).toBe("Log out")
    expect(logoutLink.prop("href")).toBe(logoutUrl.toString())
  })

  it("renders correctly for an anonymous user", async () => {
    SETTINGS.user = null
    const { wrapper } = await render()
    expect(wrapper.find(".links").exists()).toBe(false)
  })

  describe("with loaded website", () => {
    let website: Website

    beforeEach(() => {
      website = makeWebsiteDetail()
    })

    it("shows the website title", async () => {
      const { wrapper } = await render({ website: website })
      expect(wrapper.find(".site-header h2").text()).toEqual(website.title)
    })

    it("toggles the publish drawer", async () => {
      const { wrapper } = await render({ website: website })
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
})
