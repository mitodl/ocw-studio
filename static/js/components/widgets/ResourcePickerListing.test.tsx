import React from "react"
import { waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { siteApiContentListingUrl } from "../../lib/urls"
import {
  Website,
  WebsiteContentListItem,
  WebsiteContent,
} from "../../types/websites"
import {
  makeWebsiteContentDetail,
  makeWebsiteDetail,
} from "../../util/factories/websites"
import { IntegrationTestHelper } from "../../testing_utils"
import * as websiteContext from "../../context/Website"
import ResourcePickerListing from "./ResourcePickerListing"
import { ResourceType } from "../../constants"
import { assertNotNil } from "../../test_util"

jest.mock("../../context/Website")
const useWebsite = jest.mocked(websiteContext.useWebsite)

const apiResponse = (results: WebsiteContentListItem[]) => ({
  results,
  count: 2,
  next: null,
  previous: null,
})

describe("ResourcePickerListing", () => {
  let helper: IntegrationTestHelper,
    focusResourceMock: jest.Mock,
    website: Website,
    contentListingItems: {
      videos: WebsiteContent[]
      documents: WebsiteContent[]
      pages: WebsiteContent[]
      courseLists: WebsiteContent[]
    }

  beforeEach(() => {
    helper = new IntegrationTestHelper()

    focusResourceMock = jest.fn()

    website = makeWebsiteDetail()

    useWebsite.mockReturnValue(website)

    contentListingItems = {
      videos: [makeWebsiteContentDetail(), makeWebsiteContentDetail()],
      documents: [makeWebsiteContentDetail(), makeWebsiteContentDetail()],
      pages: [makeWebsiteContentDetail(), makeWebsiteContentDetail()],
      courseLists: [makeWebsiteContentDetail(), makeWebsiteContentDetail()],
    }

    helper.mockGetRequest(
      siteApiContentListingUrl
        .param({
          name: website.name,
        })
        .query({
          offset: 0,
          type: "resource",
          detailed_list: true,
          resourcetype: ResourceType.Video,
        })
        .toString(),
      apiResponse(contentListingItems.videos),
    )

    helper.mockGetRequest(
      siteApiContentListingUrl
        .param({
          name: website.name,
        })
        .query({
          offset: 0,
          type: "resource",
          search: "newfilter",
          detailed_list: true,
          resourcetype: ResourceType.Document,
        })
        .toString(),
      apiResponse(contentListingItems.documents),
    )

    helper.mockGetRequest(
      siteApiContentListingUrl
        .param({
          name: website.name,
        })
        .query({
          offset: 0,
          type: "page",
          detailed_list: true,
        })
        .toString(),
      apiResponse(contentListingItems.pages),
    )

    helper.mockGetRequest(
      siteApiContentListingUrl
        .param({
          name: "ocw-www",
        })
        .query({
          offset: 0,
          type: "course-collection",
          detailed_list: true,
        })
        .toString(),
      apiResponse(contentListingItems.courseLists),
    )
  })

  it("should fetch and display resources", async () => {
    const [{ container }] = helper.render(
      <ResourcePickerListing
        focusResource={focusResourceMock}
        contentType="resource"
        filter={null}
        resourcetype={ResourceType.Video}
        focusedResource={null}
        singleColumn={false}
      />,
    )
    await waitFor(() => {
      const items = container.querySelectorAll(
        ".resource-picker-listing .resource-item h4",
      )
      expect(Array.from(items).map((el) => el.textContent)).toEqual(
        contentListingItems.videos.map((item) => item.title),
      )
    })
  })

  it("should call focusResource prop with resources", async () => {
    const [{ container }] = helper.render(
      <ResourcePickerListing
        focusResource={focusResourceMock}
        contentType="resource"
        filter={null}
        resourcetype={ResourceType.Video}
        focusedResource={null}
        singleColumn={false}
      />,
    )
    await waitFor(() => {
      expect(
        container.querySelector(".resource-picker-listing .resource-item"),
      ).toBeInTheDocument()
    })

    const firstItem = container.querySelector(
      ".resource-picker-listing .resource-item",
    )!
    await userEvent.click(firstItem)
    expect(focusResourceMock).toHaveBeenCalledWith(
      contentListingItems.videos[0],
    )
  })

  it("should put a class on if a resource is focused", async () => {
    const [{ container }] = helper.render(
      <ResourcePickerListing
        focusResource={focusResourceMock}
        contentType="resource"
        filter={null}
        resourcetype={ResourceType.Video}
        focusedResource={contentListingItems.videos[0]}
        singleColumn={false}
      />,
    )
    await waitFor(() => {
      const firstItem = container.querySelector(".resource-item")
      expect(firstItem?.className).toBe("resource-item focused")
    })
  })

  it("should display an image for images", async () => {
    assertNotNil(contentListingItems.videos[0].metadata)
    contentListingItems.videos[0].metadata.resourcetype = ResourceType.Image
    contentListingItems.videos[0].file = "/path/to/image.jpg"
    const [{ container }] = helper.render(
      <ResourcePickerListing
        focusResource={focusResourceMock}
        contentType="resource"
        filter={null}
        resourcetype={ResourceType.Video}
        focusedResource={null}
        singleColumn={false}
      />,
    )
    await waitFor(() => {
      const img = container.querySelector(".resource-item img")
      expect(img?.getAttribute("src")).toBe("/path/to/image.jpg")
    })
  })

  it("should display a thumbnail for videos", async () => {
    assertNotNil(contentListingItems.videos[0].metadata)
    contentListingItems.videos[0].metadata.resourcetype = ResourceType.Video
    contentListingItems.videos[0].metadata.video_files = {
      video_thumbnail_file: "/path/to/image.jpg",
    }
    const [{ container }] = helper.render(
      <ResourcePickerListing
        focusResource={focusResourceMock}
        contentType="resource"
        filter={null}
        resourcetype={ResourceType.Video}
        focusedResource={null}
        singleColumn={false}
      />,
    )
    await waitFor(() => {
      const img = container.querySelector(".resource-item img")
      expect(img?.getAttribute("src")).toBe("/path/to/image.jpg")
    })
  })

  it("should fetch and display pages", async () => {
    const [{ container }] = helper.render(
      <ResourcePickerListing
        focusResource={focusResourceMock}
        contentType="page"
        filter={null}
        resourcetype={null}
        focusedResource={null}
        singleColumn={false}
      />,
    )
    await waitFor(() => {
      const items = container.querySelectorAll(
        ".resource-picker-listing .resource-item h4",
      )
      expect(Array.from(items).map((el) => el.textContent)).toEqual(
        contentListingItems.pages.map((item) => item.title),
      )
    })

    expect(helper.handleRequest).toHaveBeenCalledWith(
      siteApiContentListingUrl
        .param({ name: website.name })
        .query({
          offset: 0,
          type: "page",
          detailed_list: true,
        })
        .toString(),
      "GET",
      expect.anything(),
    )
  })

  it("should fetch and display content collections", async () => {
    const [{ container }] = helper.render(
      <ResourcePickerListing
        focusResource={focusResourceMock}
        contentType="course-collection"
        filter={null}
        resourcetype={null}
        focusedResource={null}
        singleColumn={false}
        sourceWebsiteName="ocw-www"
      />,
    )
    await waitFor(() => {
      const items = container.querySelectorAll(
        ".resource-picker-listing .resource-item h4",
      )
      expect(Array.from(items).map((el) => el.textContent)).toEqual(
        contentListingItems.courseLists.map((item) => item.title),
      )
    })

    expect(helper.handleRequest).toHaveBeenCalledWith(
      siteApiContentListingUrl
        .param({ name: "ocw-www" })
        .query({
          offset: 0,
          type: "course-collection",
          detailed_list: true,
        })
        .toString(),
      "GET",
      expect.anything(),
    )
  })

  it.each([false, true])(
    "displays pages in a single column iff singleColumn: true (case: %s)",
    async (singleColumn) => {
      const [{ container }] = helper.render(
        <ResourcePickerListing
          focusResource={focusResourceMock}
          contentType="resource"
          filter={null}
          resourcetype={ResourceType.Video}
          focusedResource={null}
          singleColumn={singleColumn}
        />,
      )
      await waitFor(() => {
        const listing = container.querySelector(".resource-picker-listing")
        expect(listing?.classList.contains("column-view")).toBe(singleColumn)
      })
    },
  )

  it.each([false, true])(
    "Includes 'Updated ...' iff singleColumn: true (case: %s)",
    async (singleColumn) => {
      const [{ container }] = helper.render(
        <ResourcePickerListing
          focusResource={focusResourceMock}
          contentType="resource"
          filter={null}
          resourcetype={ResourceType.Video}
          focusedResource={null}
          singleColumn={singleColumn}
        />,
      )
      await waitFor(() => {
        const items = container.querySelectorAll(
          ".resource-picker-listing .resource-item h4",
        )
        expect(
          Array.from(items).map((el) => el.textContent?.includes("Updated")),
        ).toStrictEqual([singleColumn, singleColumn])
      })
    },
  )

  it("should allow the user to filter, sort resourcetype", async () => {
    const [{ container }] = helper.render(
      <ResourcePickerListing
        focusResource={focusResourceMock}
        contentType="resource"
        filter="newfilter"
        resourcetype={ResourceType.Document}
        focusedResource={null}
        singleColumn={false}
      />,
    )
    await waitFor(() => {
      const items = container.querySelectorAll(
        ".resource-picker-listing .resource-item h4",
      )
      expect(Array.from(items).map((el) => el.textContent)).toEqual(
        contentListingItems.documents.map((item) => item.title),
      )
    })
  })
})
