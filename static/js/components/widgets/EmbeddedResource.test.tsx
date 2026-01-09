import React from "react"
import { waitFor } from "@testing-library/react"

import EmbeddedResource from "./EmbeddedResource"
import { IntegrationTestHelper } from "../../testing_utils"
import * as contextWebsite from "../../context/Website"
import {
  makeWebsiteContentDetail,
  makeWebsiteDetail,
} from "../../util/factories/websites"
import { Website, WebsiteContent } from "../../types/websites"
import { siteApiContentDetailUrl } from "../../lib/urls"
import { ResourceType } from "../../constants"

jest.mock("../../context/Website")
jest.mock("../../hooks/state")
const useWebsite = jest.mocked(contextWebsite.useWebsite)

describe("EmbeddedResource", () => {
  let helper: IntegrationTestHelper,
    website: Website,
    content: WebsiteContent,
    el: HTMLElement

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    website = makeWebsiteDetail()
    content = makeWebsiteContentDetail()

    useWebsite.mockReturnValue(website)

    helper.mockGetRequest(
      siteApiContentDetailUrl
        .param({ name: website.name, textId: content.text_id })
        .toString(),
      content,
    )

    el = document.createElement("div")
    document.body.appendChild(el)
  })

  afterEach(() => {
    document.body.removeChild(el)
  })

  it("should render, and display basic info about the resource", async () => {
    helper.render(<EmbeddedResource uuid={content.text_id} el={el} />)
    await waitFor(() => {
      expect(el.querySelector(".title")?.textContent).toBe(content.title)
    })
  })

  it("should render a resourcetype if it's there in the metadata", async () => {
    content.metadata!.resourcetype = ResourceType.Document
    helper.render(<EmbeddedResource uuid={content.text_id} el={el} />)
    await waitFor(() => {
      expect(el.querySelector(".resource-info")?.textContent).toBe(
        "Resourcetype: Document",
      )
    })
  })

  it("should render an image", async () => {
    content.metadata!.resourcetype = ResourceType.Image
    content.file = "https://example.com/foo/bar/baz.png"
    helper.render(<EmbeddedResource uuid={content.text_id} el={el} />)
    await waitFor(() => {
      expect(el.querySelector(".resource-info")?.textContent).toBe("baz.png")
      expect(el.querySelector("h3")?.textContent).toBe(content.title)
      expect(el.querySelector("img")?.getAttribute("src")).toBe(content.file)
    })
  })

  it("should render a video", async () => {
    content.metadata!.resourcetype = ResourceType.Video
    content.metadata!.description = "My Video!!!"
    content.metadata!.video_metadata = { youtube_id: "2XID_W4neJo" }
    helper.render(<EmbeddedResource uuid={content.text_id} el={el} />)
    await waitFor(() => {
      expect(el.querySelector(".title")?.textContent).toBe(content.title)
      expect(el.querySelector(".description")?.textContent).toBe(
        content.metadata!.description,
      )
      expect(el.querySelector("iframe")?.getAttribute("src")).toBe(
        "https://www.youtube-nocookie.com/embed/2XID_W4neJo",
      )
    })
  })
})
