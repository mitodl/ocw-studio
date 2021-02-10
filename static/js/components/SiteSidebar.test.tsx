import React from "react"
import { shallow } from "enzyme"

import SiteSidebar from "./SiteSidebar"

import { makeWebsite } from "../util/factories/websites"
import { siteUrl, siteComponentUrl } from "../lib/urls"

import { Website } from "../types/websites"

describe("SiteSidebar", () => {
  let website: Website

  beforeEach(() => {
    website = makeWebsite()
  })

  it("renders some links", () => {
    const wrapper = shallow(<SiteSidebar website={website} />)

    const links = wrapper
      .find("NavLink")
      .map(link => [link.text(), link.prop("to")])

    const expected = [
      ["Content", siteUrl(website.name)],
      ["Page", siteComponentUrl(website.name, "page")],
      ["Resource", siteComponentUrl(website.name, "resource")]
    ]

    expect(expected).toEqual(expect.arrayContaining(links))
  })
})
