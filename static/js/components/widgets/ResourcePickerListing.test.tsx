import { siteApiContentListingUrl } from "../../lib/urls"
import { Website, WebsiteContentListItem } from "../../types/websites"
import {
  makeWebsiteContentListItem,
  makeWebsiteDetail
} from "../../util/factories/websites"
import IntegrationTestHelper, {
  TestRenderer
} from "../../util/integration_test_helper"
import { useWebsite } from "../../context/Website"
import ResourcePickerListing from "./ResourcePickerListing"
import {RESOURCE_TYPE_DOCUMENT, RESOURCE_TYPE_VIDEO} from "../../constants";

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
      [makeWebsiteContentListItem(), makeWebsiteContentListItem()],
      [makeWebsiteContentListItem(), makeWebsiteContentListItem()]
    ]

    helper.mockGetRequest(
      siteApiContentListingUrl
        .param({
          name: website.name
        })
        .query({ offset: 0, type: "resource", resourcetype: RESOURCE_TYPE_VIDEO })
        .toString(),
      apiResponse(contentListingItems[0])
    )

    helper.mockGetRequest(
      siteApiContentListingUrl
        .param({
          name: website.name
        })
        .query({
          offset:       0,
          type:         "resource",
          search:       "newfilter",
          resourcetype: RESOURCE_TYPE_DOCUMENT
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
    expect(
      focusResourceStub.calledWith(contentListingItems[0][0].text_id)
    ).toBeTruthy()
    wrapper.update()
  })

  it("should put a class on if a resource is focused", async () => {
    const { wrapper } = await render({
      focusedResource: contentListingItems[0][0].text_id
    })

    expect(
      wrapper
        .find(".resource-item")
        .at(0)
        .prop("className")
    ).toBe("resource-item focused")
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
