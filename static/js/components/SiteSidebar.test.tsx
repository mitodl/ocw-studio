import React from "react"
import { shallow } from "enzyme"

import SiteSidebar from "./SiteSidebar"

import { makeWebsiteDetail } from "../util/factories/websites"
import { siteContentListingUrl } from "../lib/urls"

import { Website } from "../types/websites"
import { CONTENT_TYPE_PAGE, CONTENT_TYPE_RESOURCE } from "../constants"

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
          .param({ name: website.name, contentType: CONTENT_TYPE_PAGE })
          .toString()
      ],
      [
        "Resource",
        siteContentListingUrl
          .param({ name: website.name, contentType: CONTENT_TYPE_RESOURCE })
          .toString()
      ]
    ]

    expect(links).toEqual(expect.arrayContaining(expected))
  })
})
