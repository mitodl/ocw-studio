import {
  newSiteUrl,
  siteAddContentUrl,
  siteApiContentCreateUrl,
  siteApiContentDetailUrl,
  siteApiContentListingUrl,
  siteApiDetailUrl,
  siteApiListingUrl,
  siteContentListingUrl,
  siteDetailUrl,
  siteListingUrl
} from "./urls"
import { CONTENT_TYPE_PAGE, CONTENT_TYPE_RESOURCE } from "../constants"

describe("urls", () => {
  [
    [0, "/sites/"],
    [20, "/sites/?offset=20"]
  ].forEach(([offset, expectedLink]) => {
    it(`renders a URL for the site dashboard with offset=${offset}`, () => {
      // @ts-ignore
      expect(siteListingUrl(offset)).toBe(expectedLink)
    })
  })

  it("makes a URL for creating new sites", () => {
    expect(newSiteUrl()).toBe("/new-site/")
  })

  it("renders a site URL", () => {
    expect(siteDetailUrl("course-name")).toBe("/sites/course-name/")
  })

  //
  ;[
    [0, "site-name", "page", "/sites/site-name/page/"],
    [20, "course-name", "resource", "/sites/course-name/resource/?offset=20"]
  ].forEach(([offset, siteName, contentType, expectedLink]) => {
    it(`renders a site listing URL with offset=${offset}`, () => {
      // @ts-ignore
      expect(siteContentListingUrl(siteName, contentType, offset)).toBe(
        expectedLink
      )
    })
  })

  it("renders a URL for adding new content", () => {
    expect(siteAddContentUrl("course-name", CONTENT_TYPE_PAGE)).toBe(
      "/sites/course-name/page/add/"
    )
  })

  describe("apis", () => {
    it("renders a URL for site listing", () => {
      expect(siteApiListingUrl(20)).toBe("/api/websites/?limit=10&offset=20")
    })

    it("renders a URL for site detail", () => {
      expect(siteApiDetailUrl("course-name")).toBe("/api/websites/course-name/")
    })

    it(`renders a URL for site content listing`, () => {
      expect(
        siteApiContentListingUrl("course-name", CONTENT_TYPE_RESOURCE, 20)
      ).toBe(
        "/api/websites/course-name/content/?type=resource&limit=10&offset=20"
      )
    })

    it("renders a URL for site content detail", () => {
      expect(siteApiContentDetailUrl("course-name", "uuid")).toBe(
        "/api/websites/course-name/content/uuid/"
      )
    })

    it("renders a URL for creating new sites", () => {
      expect(siteApiContentCreateUrl("site-name")).toBe(
        "/api/websites/site-name/content/"
      )
    })
  })
})
