import EmbeddedResource from "./EmbeddedResource"
import IntegrationTestHelper, {
  TestRenderer
} from "../../util/integration_test_helper"
import { useWebsite } from "../../context/Website"
import {
  makeWebsiteContentDetail,
  makeWebsiteDetail
} from "../../util/factories/websites"
import { Website, WebsiteContent } from "../../types/websites"
import { siteApiContentDetailUrl } from "../../lib/urls"
import { RESOURCE_TYPE_IMAGE, RESOURCE_TYPE_VIDEO } from "../../constants"

jest.mock("../../context/Website")
jest.mock("../../hooks/state")

describe("EmbeddedResource", () => {
  let helper: IntegrationTestHelper,
    render: TestRenderer,
    website: Website,
    content: WebsiteContent,
    el

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    website = makeWebsiteDetail()
    content = makeWebsiteContentDetail()
    // @ts-ignore
    useWebsite.mockReturnValue(website)

    helper.mockGetRequest(
      siteApiContentDetailUrl
        .param({ name: website.name, textId: content.text_id })
        .toString(),
      content
    )

    el = document.createElement("div")
    render = helper.configureRenderer(EmbeddedResource, {
      uuid: content.text_id,
      el
    })
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("should render, and display basic info about the resource", async () => {
    const { wrapper } = await render()
    expect(wrapper.find(".title").text()).toBe(content.title)
  })

  it("should render a filetype if it's there in the metadata", async () => {
    content.metadata!.filetype = "PDF"
    const { wrapper } = await render()
    expect(wrapper.find(".resource-info").text()).toBe("Filetype: PDF")
  })

  it("should render an image", async () => {
    content.metadata!.filetype = RESOURCE_TYPE_IMAGE
    content.file = "https://example.com/foo/bar/baz.png"
    const { wrapper } = await render()
    expect(wrapper.find(".resource-info").text()).toBe("baz.png")
    expect(wrapper.find("h3").text()).toBe(content.title)
    expect(wrapper.find("img").prop("src")).toBe(content.file)
  })

  it("should render a video", async () => {
    content.metadata!.filetype = RESOURCE_TYPE_VIDEO
    content.metadata!.description = "My Video!!!"
    content.metadata!.video_metadata = { youtube_id: "2XID_W4neJo" }
    const { wrapper } = await render()
    expect(wrapper.find(".title").text()).toBe(content.title)
    expect(wrapper.find(".description").text()).toBe(
      content.metadata!.description
    )
    expect(wrapper.find("iframe").prop("src")).toBe(
      "https://www.youtube-nocookie.com/embed/2XID_W4neJo"
    )
  })
})
