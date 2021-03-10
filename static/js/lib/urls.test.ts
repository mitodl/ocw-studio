import {
  siteAddContentUrl,
  siteApiContentDetailUrl,
  siteApiContentUrl,
  siteApiUrl,
  siteContentListingUrl,
  siteUrl
} from "./urls"
import { CONTENT_TYPE_PAGE, CONTENT_TYPE_RESOURCE } from "../constants"

describe("urls", () => {
  it("renders a site URL", () => {
    expect(siteUrl("course-name")).toBe("/sites/course-name/")
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
      expect(siteApiUrl("course-name")).toBe("/api/websites/course-name/")
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
