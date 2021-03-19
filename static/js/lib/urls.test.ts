import {
  sitesBaseUrl,
  newSiteUrl,
  siteDetailUrl,
  siteContentListingUrl,
  siteAddContentUrl,
  siteCollaboratorsUrl,
  siteCollaboratorsAddUrl,
  siteCollaboratorsDetailUrl,
  siteApi,
  siteApiDetailUrl,
  siteApiListingUrl,
  siteApiCollaboratorsUrl,
  siteApiCollaboratorsDetailUrl,
  siteApiContentUrl,
  siteApiContentDetailUrl,
  siteApiContentListingUrl
} from "./urls"

describe("urls", () => {
  describe("Page URLs", () => {
    describe("Site URLs", () => {
      [
        [10, "/sites/?offset=10"],
        [20, "/sites/?offset=20"]
      ].forEach(([offset, expectedLink]) => {
        it(`renders a URL for the site dashboard with offset=${offset}`, () => {
          expect(sitesBaseUrl.query({ offset }).toString()).toBe(expectedLink)
        })
      })

      it("returns a basic URL for the site dashboard", () => {
        expect(sitesBaseUrl.toString()).toBe("/sites/")
      })

      it("makes a URL for creating new sites", () => {
        expect(newSiteUrl.toString()).toBe("/new-site/")
      })

      it("renders a site URL", () => {
        expect(siteDetailUrl.param({ name: "site-name" }).toString()).toBe(
          "/sites/site-name/"
        )
      })

      it("renders a site listing URL", () => {
        expect(
          siteContentListingUrl
            .param({ name: "site-name", contentType: "resource" })
            .toString()
        ).toBe("/sites/site-name/resource/")
      })

      it("renders a URL for adding new content", () => {
        expect(
          siteAddContentUrl
            .param({
              name:        "site-name",
              contentType: "page"
            })
            .toString()
        ).toBe("/sites/site-name/page/add/")
      })

      it("renders a URL for collaborators", () => {
        expect(
          siteCollaboratorsUrl.param({ name: "site-name" }).toString()
        ).toBe("/sites/site-name/collaborators/")
      })

      it("renders a URL for adding collaborators", () => {
        expect(
          siteCollaboratorsAddUrl.param({ name: "site-name" }).toString()
        ).toBe("/sites/site-name/collaborators/new/")
      })

      it("renders a URL for collaborators detail", () => {
        expect(
          siteCollaboratorsDetailUrl
            .param({ name: "site-name", username: "badoop" })
            .toString()
        ).toBe("/sites/site-name/collaborators/badoop/")
      })
    })
  })

  describe("apis", () => {
    describe("Website APIs", () => {
      it("renders a top-level site API", () => {
        expect(siteApi.toString()).toBe("/api/websites/")
      })
      it("renders a URL for site listing", () => {
        expect(siteApiListingUrl.query({ offset: 20 }).toString()).toBe(
          "/api/websites/?limit=10&offset=20"
        )
      })

      it("renders a URL for site detail", () => {
        expect(siteApiDetailUrl.param({ name: "site-name" }).toString()).toBe(
          "/api/websites/site-name/"
        )
      })

      it("renders a URL for site collaborators", () => {
        expect(
          siteApiCollaboratorsUrl.param({ name: "site-name" }).toString()
        ).toBe("/api/websites/site-name/collaborators/")
      })

      it("renders a collaborator detail URL", () => {
        expect(
          siteApiCollaboratorsDetailUrl
            .param({
              name:     "site-name",
              username: "greatusername"
            })
            .toString()
        ).toBe("/api/websites/site-name/collaborators/greatusername/")
      })

      it("renders a URL for site content listing", () => {
        expect(siteApiContentUrl.param({ name: "site-name" }).toString()).toBe(
          "/api/websites/site-name/content/"
        )
      })

      it("renders a URL for site content detail", () => {
        expect(
          siteApiContentDetailUrl
            .param({ name: "site-name", uuid: "uuid" })
            .toString()
        ).toBe("/api/websites/site-name/content/uuid/")
      })

      it("should render a content listing URL", () => {
        expect(
          siteApiContentListingUrl
            .param({ name: "the-best-course" })
            .query({ offset: 40 })
            .toString()
        ).toBe("/api/websites/the-best-course/content/?limit=10&offset=40")
      })
    })
  })
})
