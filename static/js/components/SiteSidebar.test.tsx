import React from "react"
import { shallow } from "enzyme"

import SiteSidebar from "./SiteSidebar"

import { makeWebsiteDetail } from "../util/factories/websites"
import { siteCollaboratorsUrl, siteContentListingUrl } from "../lib/urls"

import { Website } from "../types/websites"

describe("SiteSidebar", () => {
  let website: Website

  beforeEach(() => {
    website = makeWebsiteDetail()
  })

  it("renders some links", () => {
    const wrapper = shallow(<SiteSidebar website={website} />)

    const links = wrapper
      .find("NavLink")
      .map(link => [link.text(), link.prop("to")])

    const expected = [
      [
        "Page",
        siteContentListingUrl
          .param({
            name:        website.name,
            contentType: "page"
          })
          .toString()
      ],
      [
        "Resource",
        siteContentListingUrl
          .param({
            name:        website.name,
            contentType: "resource"
          })
          .toString()
      ],
      [
        "Site Metadata",
        siteContentListingUrl
          .param({
            name:        website.name,
            contentType: "metadata"
          })
          .toString()
      ]
    ]

    expect(links).toEqual(expect.arrayContaining(expected))
  })

  it("renders a collaborators link if the user is an admin for the given website", () => {
    website.is_admin = true
    const wrapper = shallow(<SiteSidebar website={website} />)

    const collaboratorLinkUrl = siteCollaboratorsUrl
      .param({ name: website.name })
      .toString()
    expect(wrapper.find("NavLink").some({ to: collaboratorLinkUrl })).toBe(true)
  })
})
