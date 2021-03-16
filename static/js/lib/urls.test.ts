import {
  sitesBaseUrl,
  newSiteUrl,
  siteDetailUrl,
  siteSettingsUrl,
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
import { CONTENT_TYPE_PAGE, CONTENT_TYPE_RESOURCE } from "../constants"

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

      it("renders a settings url", () => {
        expect(
          siteSettingsUrl.param({ name: "a-better-course" }).toString()
        ).toBe("/sites/a-better-course/settings/")
      })

      it("renders a site URL", () => {
        expect(siteDetailUrl.param({ name: "course-name" }).toString()).toBe(
          "/sites/course-name/"
        )
      })

      it("renders a site listing URL", () => {
        expect(
          siteContentListingUrl
            .param({ name: "course-name", contentType: CONTENT_TYPE_RESOURCE })
            .toString()
        ).toBe("/sites/course-name/resource/")
      })

      it("renders a URL for adding new content", () => {
        expect(
          siteAddContentUrl
            .param({
              name:        "course-name",
              contentType: CONTENT_TYPE_PAGE
            })
            .toString()
        ).toBe("/sites/course-name/page/add/")
      })

      it("renders a URL for collaborators", () => {
        expect(
          siteCollaboratorsUrl.param({ name: "course-name" }).toString()
        ).toBe("/sites/course-name/settings/collaborators/")
      })

      it("renders a URL for adding collaborators", () => {
        expect(
          siteCollaboratorsAddUrl.param({ name: "course-name" }).toString()
        ).toBe("/sites/course-name/settings/collaborators/new/")
      })

      it("renders a URL for collaborators detail", () => {
        expect(
          siteCollaboratorsDetailUrl
            .param({ name: "course-name", username: "badoop" })
            .toString()
        ).toBe("/sites/course-name/settings/collaborators/badoop/")
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
        expect(siteApiDetailUrl.param({ name: "course-name" }).toString()).toBe(
          "/api/websites/course-name/"
        )
      })

      it("renders a URL for site collaborators", () => {
        expect(
          siteApiCollaboratorsUrl.param({ name: "course-name" }).toString()
        ).toBe("/api/websites/course-name/collaborators/")
      })

      it("renders a collaborator detail URL", () => {
        expect(
          siteApiCollaboratorsDetailUrl
            .param({
              name:     "course-name",
              username: "greatusername"
            })
            .toString()
        ).toBe("/api/websites/course-name/collaborators/greatusername/")
      })

      it("renders a URL for site content listing", () => {
        expect(
          siteApiContentUrl.param({ name: "course-name" }).toString()
        ).toBe("/api/websites/course-name/content/")
      })

      it("renders a URL for site content detail", () => {
        expect(
          siteApiContentDetailUrl
            .param({ name: "course-name", uuid: "uuid" })
            .toString()
        ).toBe("/api/websites/course-name/content/uuid/")
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
