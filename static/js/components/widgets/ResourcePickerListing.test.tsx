import { siteApiContentListingUrl } from "../../lib/urls"
import { Website, WebsiteContentListItem } from "../../types/websites"
import {
  makeWebsiteContentDetail,
  makeWebsiteDetail
} from "../../util/factories/websites"
import IntegrationTestHelper, {
  TestRenderer
} from "../../util/integration_test_helper"
import { useWebsite } from "../../context/Website"
import ResourcePickerListing from "./ResourcePickerListing"
import {
  RESOURCE_TYPE_DOCUMENT,
  RESOURCE_TYPE_IMAGE,
  RESOURCE_TYPE_VIDEO
} from "../../constants"

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
    contentListingItems: WebsiteContentListItem[][]

  beforeEach(() => {
    helper = new IntegrationTestHelper()

    focusResourceStub = helper.sandbox.stub()
    setOpenStub = helper.sandbox.stub()

    render = helper.configureRenderer(ResourcePickerListing, {
      focusResource: focusResourceStub,
      setOpen:       setOpenStub,
      attach:        "resource",
      filter:        null,
      resourcetype:  RESOURCE_TYPE_VIDEO
    })

    website = makeWebsiteDetail()
    // @ts-ignore
    useWebsite.mockReturnValue(website)

    contentListingItems = [
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
          resourcetype:  RESOURCE_TYPE_VIDEO
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
          resourcetype:  RESOURCE_TYPE_DOCUMENT
        })
        .toString(),
      apiResponse(contentListingItems[1])
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
    contentListingItems[0][0].metadata.resourcetype = RESOURCE_TYPE_IMAGE
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
    contentListingItems[0][0].metadata.resourcetype = RESOURCE_TYPE_VIDEO
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

  it("should allow the user to filter, sort resourcetype", async () => {
    const { wrapper } = await render({
      filter:       "newfilter",
      resourcetype: RESOURCE_TYPE_DOCUMENT
    })

    expect(
      wrapper
        .find(".resource-picker-listing .resource-item")
        .map(el => el.find("h4").text())
    ).toEqual(contentListingItems[1].map(item => item.title))
  })
})
