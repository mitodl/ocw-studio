import React from "react"
import { screen } from "@testing-library/react"

import SiteSidebar from "./SiteSidebar"

import {
  makeWebsiteDetail,
  makeTopLevelConfigItem,
} from "../util/factories/websites"
import { times } from "lodash"
import { siteCollaboratorsUrl, siteContentListingUrl } from "../lib/urls"
import { IntegrationTestHelper } from "../testing_utils"

import { Website } from "../types/websites"

describe("SiteSidebar", () => {
  let website: Website, helper: IntegrationTestHelper

  beforeEach(() => {
    website = makeWebsiteDetail()
    helper = new IntegrationTestHelper()
  })
  ;[true, false].forEach((isAdminUser) => {
    it(`renders ${isAdminUser ? "all" : "non-admin"} links`, async () => {
      website.is_admin = isAdminUser
      helper.renderWithWebsite(<SiteSidebar website={website} />, website)

      const expected = [
        [
          "Pages",
          siteContentListingUrl
            .param({
              name: website.name,
              contentType: "page",
            })
            .toString(),
        ],
        [
          "Resources",
          siteContentListingUrl
            .param({
              name: website.name,
              contentType: "resource",
            })
            .toString(),
        ],
        [
          "Menu",
          siteContentListingUrl
            .param({
              name: website.name,
              contentType: "menu",
            })
            .toString(),
        ],
      ]
      if (isAdminUser) {
        expected.splice(2, 0, [
          "Metadata",
          siteContentListingUrl
            .param({
              name: website.name,
              contentType: "metadata",
            })
            .toString(),
        ])
      }

      for (const [text, href] of expected) {
        const link = screen.getByRole("link", { name: text })
        expect(link).toHaveAttribute("href", href)
      }
    })
  })

  it("should pad all .config-sections excepting the last one", async () => {
    website.is_admin = false
    website.starter!.config!.collections = times(5).map((idx) =>
      makeTopLevelConfigItem(`foobar${idx}`, null, `category${idx}`),
    )
    const [{ container }] = helper.renderWithWebsite(
      <SiteSidebar website={website} />,
      website,
    )
    const sections = container.querySelectorAll(".sidebar-section")
    const classNames = Array.from(sections).map((el) => el.className)
    expect(classNames).toEqual([
      "sidebar-section pb-4",
      "sidebar-section pb-4",
      "sidebar-section pb-4",
      "sidebar-section pb-4",
      "sidebar-section",
    ])
  })

  it("renders a collaborators link if the user is an admin for the given website", async () => {
    website.is_admin = true
    helper.renderWithWebsite(<SiteSidebar website={website} />, website)

    const collaboratorLinkUrl = siteCollaboratorsUrl
      .param({ name: website.name })
      .toString()
    const collaboratorLink = screen.getByRole("link", { name: "Collaborators" })
    expect(collaboratorLink).toHaveAttribute("href", collaboratorLinkUrl)
  })
})
