import { makeWebsiteDetail } from "../util/factories/websites"
import { useWebsiteContent } from "../hooks/websites"
import { IntegrationTestHelper } from "../testing_utils"
import GenericContentReroutePage from "./GenericContentReroutePage"
import { waitFor } from "@testing-library/react"
import React from "react"

jest.mock("../hooks/websites")

describe("GenericContentReroutePage", () => {
  const mockWebsite = makeWebsiteDetail({
    name: "test-site",
    uuid: "website-uuid",
    title: "Test Site",
  })

  const helper = new IntegrationTestHelper()
  helper.mockGetWebsiteDetail(mockWebsite)

  const testCases = [
    {
      type: "page",
      expectedPath: "/sites/test-site/type/page/edit/test-uuid/",
    },
    {
      type: "video_gallery",
      expectedPath: "/sites/test-site/type/video_gallery/edit/test-uuid/",
    },
    {
      type: "external_resource",
      expectedPath: "/sites/test-site/type/external_resource/edit/test-uuid/",
    },
  ]

  testCases.forEach(({ type, expectedPath }) => {
    it(`reroutes to the correct page based on content type: ${type}`, async () => {
      const mockResource = {
        type,
        text_id: "test-uuid",
      }

      ;(useWebsiteContent as jest.Mock).mockReturnValue([mockResource])

      const [_, { history }] = helper.renderWithWebsite(
        <GenericContentReroutePage />,
        mockWebsite,
      )

      await waitFor(() => {
        expect(history.location.pathname).toBe(expectedPath)
      })
    })
  })
})
