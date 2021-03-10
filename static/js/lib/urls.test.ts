import {
  newSiteUrl,
  siteAddContentUrl,
  siteApiContentDetailUrl,
  siteApiContentUrl,
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

  it("renders a site listing URL", () => {
    expect(siteContentListingUrl("course-name", CONTENT_TYPE_RESOURCE)).toBe(
      "/sites/course-name/resource/"
    )
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

    it("renders a URL for site content listing", () => {
      expect(siteApiContentUrl("course-name")).toBe(
        "/api/websites/course-name/content/"
      )
    })

    it("renders a URL for site content detail", () => {
      expect(siteApiContentDetailUrl("course-name", "uuid")).toBe(
        "/api/websites/course-name/content/uuid/"
      )
    })
  })
})
