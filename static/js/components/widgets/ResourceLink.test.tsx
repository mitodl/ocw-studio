import ResourceLink from "./ResourceLink"
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
import {
  RESOURCE_TYPE_DOCUMENT,
  RESOURCE_TYPE_IMAGE,
  RESOURCE_TYPE_OTHER,
  RESOURCE_TYPE_VIDEO
} from "../../constants"

jest.mock("../../context/Website")
jest.mock("../../hooks/state")

describe("ResourceLink", () => {
  let helper: IntegrationTestHelper,
    render: TestRenderer,
    website: Website,
    content: WebsiteContent,
    el: HTMLDivElement

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
    render = helper.configureRenderer(ResourceLink, {
      uuid: content.text_id,
      el
    })
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("should render, display some basic information about the resource", async () => {
    const { wrapper } = await render()
    expect(wrapper.text().includes(content.title as string)).toBeTruthy()
  })

  //
  ;[
    [RESOURCE_TYPE_IMAGE, "image"],
    [RESOURCE_TYPE_VIDEO, "movie"],
    [RESOURCE_TYPE_DOCUMENT, "description"],
    [RESOURCE_TYPE_OTHER, "attachment"]
  ].forEach(([resourceType, iconName]) => {
    it(`should render an appropriate icon for ${resourceType}`, async () => {
      content.metadata!.filetype = resourceType
      const { wrapper } = await render()
      expect(wrapper.find("i").text()).toBe(iconName)
    })
  })
})
