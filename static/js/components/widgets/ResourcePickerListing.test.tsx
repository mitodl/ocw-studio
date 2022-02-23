import sinon from "sinon"
import { siteApiContentListingUrl } from "../../lib/urls"
import {
  Website,
  WebsiteContentListItem,
  WebsiteContent
} from "../../types/websites"
import {
  makeWebsiteContentDetail,
  makeWebsiteDetail
} from "../../util/factories/websites"
import IntegrationTestHelper, {
  TestRenderer
} from "../../util/integration_test_helper"
import { useWebsite } from "../../context/Website"
import ResourcePickerListing from "./ResourcePickerListing"
import { ResourceType } from "../../constants"

jest.mock("../../context/Website")

const apiResponse = (results: WebsiteContentListItem[]) => ({
  results,
  count:    2,
  next:     null,
  previous: null
})

describe("ResourcePickerListing", () => {
  let helper: IntegrationTestHelper,
    render: TestRenderer,
    focusResourceStub: any,
    setOpenStub: any,
    website: Website,
    contentListingItems: WebsiteContent[][]

  beforeEach(() => {
    helper = new IntegrationTestHelper()

    focusResourceStub = helper.sandbox.stub()
    setOpenStub = helper.sandbox.stub()

    render = helper.configureRenderer(ResourcePickerListing, {
      focusResource: focusResourceStub,
      setOpen:       setOpenStub,
      contentType:   "resource",
      filter:        null,
      resourcetype:  ResourceType.Video
    })

    website = makeWebsiteDetail()
    // @ts-ignore
    useWebsite.mockReturnValue(website)

    contentListingItems = [
      [makeWebsiteContentDetail(), makeWebsiteContentDetail()],
      [makeWebsiteContentDetail(), makeWebsiteContentDetail()],
      [makeWebsiteContentDetail(), makeWebsiteContentDetail()],
      [makeWebsiteContentDetail(), makeWebsiteContentDetail()]
    ]

    helper.mockGetRequest(
      siteApiContentListingUrl
        .param({
          name: website.name
        })
        .query({
          offset:        0,
          type:          "resource",
          detailed_list: true,
          resourcetype:  ResourceType.Video
        })
        .toString(),
      apiResponse(contentListingItems[0])
    )

    helper.mockGetRequest(
      siteApiContentListingUrl
        .param({
          name: website.name
        })
        .query({
          offset:        0,
          type:          "resource",
          search:        "newfilter",
          detailed_list: true,
          resourcetype:  ResourceType.Document
        })
        .toString(),
      apiResponse(contentListingItems[1])
    )

    helper.mockGetRequest(
      siteApiContentListingUrl
        .param({
          name: website.name
        })
        .query({
          offset:        0,
          type:          "page",
          detailed_list: true
        })
        .toString(),
      apiResponse(contentListingItems[2])
    )

    helper.mockGetRequest(
      siteApiContentListingUrl
        .param({
          name: "ocw-www"
        })
        .query({
          offset:        0,
          type:          "course_collections",
          detailed_list: true
        })
        .toString(),
      apiResponse(contentListingItems[3])
    )
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("should fetch and display resources", async () => {
    const { wrapper } = await render()
    expect(
      wrapper
        .find(".resource-picker-listing .resource-item")
        .map(el => el.find("h4").text())
    ).toEqual(contentListingItems[0].map(item => item.title))
  })

  it("should call focusResource prop with resources", async () => {
    const { wrapper } = await render()

    wrapper
      .find(".resource-picker-listing .resource-item")
      .at(0)
      .simulate("click")
    expect(focusResourceStub.calledWith(contentListingItems[0][0])).toBeTruthy()
    wrapper.update()
  })

  it("should put a class on if a resource is focused", async () => {
    const { wrapper } = await render({
      focusedResource: contentListingItems[0][0]
    })

    expect(
      wrapper
        .find(".resource-item")
        .at(0)
        .prop("className")
    ).toBe("resource-item focused")
  })

  it("should display an image for images", async () => {
    // @ts-ignore
    contentListingItems[0][0].metadata.resourcetype = ResourceType.Image
    // @ts-ignore
    contentListingItems[0][0].file = "/path/to/image.jpg"
    const { wrapper } = await render()
    expect(
      wrapper
        .find(".resource-item")
        .at(0)
        .find("img")
        .prop("src")
    ).toBe("/path/to/image.jpg")
  })

  it("should display a thumbnail for videos", async () => {
    // @ts-ignore
    contentListingItems[0][0].metadata.resourcetype = ResourceType.Video
    // @ts-ignore
    contentListingItems[0][0].metadata.video_files = {
      video_thumbnail_file: "/path/to/image.jpg"
    }
    const { wrapper } = await render()
    expect(
      wrapper
        .find(".resource-item")
        .at(0)
        .find("img")
        .prop("src")
    ).toBe("/path/to/image.jpg")
  })

  it("should fetch and display pages", async () => {
    const { wrapper } = await render({
      contentType:  "page",
      resourcetype: null
    })
    expect(
      wrapper
        .find(".resource-picker-listing .resource-item")
        .map(el => el.find("h4").text())
    ).toEqual(contentListingItems[2].map(item => item.title))

    sinon.assert.calledWith(
      helper.handleRequestStub,
      siteApiContentListingUrl
        .param({ name: website.name })
        .query({
          offset:        0,
          type:          "page",
          detailed_list: true
        })
        .toString()
    )
  })

  it("should fetch and display content collections", async () => {
    const { wrapper } = await render({
      contentType:       "course_collections",
      resourcetype:      null,
      sourceWebsiteName: "ocw-www"
    })
    expect(
      wrapper
        .find(".resource-picker-listing .resource-item")
        .map(el => el.find("h4").text())
    ).toEqual(contentListingItems[3].map(item => item.title))

    sinon.assert.calledWith(
      helper.handleRequestStub,
      siteApiContentListingUrl
        .param({ name: "ocw-www" })
        .query({
          offset:        0,
          type:          "course_collections",
          detailed_list: true
        })
        .toString()
    )
  })

  it.each([false, true])(
    "displays pages in a single column iff singleColumn: true (case: %s)",
    async singleColumn => {
      const { wrapper } = await render({ singleColumn })
      expect(
        wrapper.find(".resource-picker-listing").hasClass("column-view")
      ).toBe(singleColumn)
    }
  )

  it("should allow the user to filter, sort resourcetype", async () => {
    const { wrapper } = await render({
      filter:       "newfilter",
      resourcetype: ResourceType.Document
    })

    expect(
      wrapper
        .find(".resource-picker-listing .resource-item")
        .map(el => el.find("h4").text())
    ).toEqual(contentListingItems[1].map(item => item.title))
  })
})
