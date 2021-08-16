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
    expect(wrapper.find(".filetype").text()).toBe("Filetype: PDF")
  })
})
