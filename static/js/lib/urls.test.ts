import { siteContentListingUrl, siteUrl } from "./urls"

describe("urls", () => {
  it("renders a site URL", () => {
    expect(siteUrl("course-name")).toBe("/sites/course-name/")
  })

  it("renders a site content listing URL", () => {
    expect(siteContentListingUrl("course-name", "resource")).toBe(
      "/sites/course-name/resource/"
    )
  })
})
