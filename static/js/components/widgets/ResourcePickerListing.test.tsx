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
    insertEmbedStub: any,
    setOpenStub: any,
    website: Website,
    contentListingItems: WebsiteContentListItem[][]

  beforeEach(() => {
    helper = new IntegrationTestHelper()

    insertEmbedStub = helper.sandbox.stub()
    setOpenStub = helper.sandbox.stub()

    render = helper.configureRenderer(ResourcePickerListing, {
      insertEmbed: insertEmbedStub,
      setOpen:     setOpenStub,
      attach:      "resource",
      filter:      null,
      filetype:    "Video"
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
        .query({ offset: 0, type: "resource", filetype: "Video" })
        .toString(),
      apiResponse(contentListingItems[0])
    )

    helper.mockGetRequest(
      siteApiContentListingUrl
        .param({
          name: website.name
        })
        .query({
          offset:   0,
          type:     "resource",
          search:   "newfilter",
          filetype: "Document"
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

  it("should call insertEmbed prop with resources", async () => {
    const { wrapper } = await render()

    wrapper
      .find(".resource-picker-listing .resource-item")
      .at(0)
      .simulate("click")
    expect(
      insertEmbedStub.calledWith(contentListingItems[0][0].text_id)
    ).toBeTruthy()
  })

  it("should allow the user to filter, sort filetype", async () => {
    const { wrapper } = await render({
      filter:   "newfilter",
      filetype: "Document"
    })

    expect(
      wrapper
        .find(".resource-picker-listing .resource-item")
        .map(el => el.find("h4").text())
    ).toEqual(contentListingItems[1].map(item => item.title))
  })
})
