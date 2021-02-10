import { siteComponentUrl, siteUrl } from "./urls"

describe("urls", () => {
  it("renders a site URL", () => {
    expect(siteUrl("course-name")).toBe("/sites/course-name/")
  })

  it("renders a site component URL", () => {
    expect(siteComponentUrl("course-name", "resource")).toBe(
      "/sites/course-name/resource/"
    )
  })
})
