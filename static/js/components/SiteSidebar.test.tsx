import SiteSidebar from "./SiteSidebar"

import {
  makeWebsiteDetail,
  makeTopLevelConfigItem
} from "../util/factories/websites"
import { times } from "lodash"
import { siteCollaboratorsUrl, siteContentListingUrl } from "../lib/urls"
import IntegrationTestHelper, {
  TestRenderer
} from "../util/integration_test_helper"

import { Website } from "../types/websites"

describe("SiteSidebar", () => {
  let website: Website, helper: IntegrationTestHelper, render: TestRenderer

  beforeEach(() => {
    website = makeWebsiteDetail()
    helper = new IntegrationTestHelper()
    render = helper.configureRenderer(SiteSidebar, { website })
  })

  afterEach(() => {
    helper.cleanup()
  })
  ;[true, false].forEach(isAdminUser => {
    it(`renders ${isAdminUser ? "all" : "non-admin"} links`, async () => {
      website.is_admin = isAdminUser
      const { wrapper } = await render()

      const links = wrapper
        .find("NavLink")
        .map(link => [link.text(), link.prop("to")])

      const expected = [
        [
          "Pages",
          siteContentListingUrl
            .param({
              name:        website.name,
              contentType: "page"
            })
            .toString()
        ],
        [
          "Resources",
          siteContentListingUrl
            .param({
              name:        website.name,
              contentType: "resource"
            })
            .toString()
        ],
        [
          "Menu",
          siteContentListingUrl
            .param({
              name:        website.name,
              contentType: "menu"
            })
            .toString()
        ]
      ]
      if (isAdminUser) {
        expected.splice(2, 0, [
          "Metadata",
          siteContentListingUrl
            .param({
              name:        website.name,
              contentType: "metadata"
            })
            .toString()
        ])
      }
      expect(links).toEqual(expect.arrayContaining(expected))
    })
  })

  it("should pad all .config-sections excepting the last one", async () => {
    website.is_admin = false // Prevent an extra section getting added if true
    website.starter!.config!.collections = times(5).map(idx =>
      makeTopLevelConfigItem(`foobar${idx}`, null, `category${idx}`)
    )
    const { wrapper } = await render()
    expect(
      wrapper
        .find("SidebarSection")
        .map(wrapper => wrapper.find("div").prop("className"))
    ).toEqual([
      "sidebar-section pb-4",
      "sidebar-section pb-4",
      "sidebar-section pb-4",
      "sidebar-section pb-4",
      "sidebar-section"
    ])
  })

  it("renders a collaborators link if the user is an admin for the given website", async () => {
    website.is_admin = true
    const { wrapper } = await render()

    const collaboratorLinkUrl = siteCollaboratorsUrl
      .param({ name: website.name })
      .toString()
    expect(wrapper.find("NavLink").some({ to: collaboratorLinkUrl })).toBe(true)
  })
})
