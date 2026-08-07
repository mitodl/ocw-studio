import LinkPlugin from "@ckeditor/ckeditor5-link/src/link"
import { LinkUI } from "@ckeditor/ckeditor5-link"
import ParagraphPlugin from "@ckeditor/ckeditor5-paragraph/src/paragraph"

import ResourceLinkUI from "./ResourceLinkUI"
import { createTestEditor } from "./test_util"
import { RESOURCE_LINK_CONFIG_KEY } from "./constants"

/**
 * Characterization tests. ResourceLinkUI depends on internals of CKEditor's
 * LinkUI plugin, so these pin down the shape it relies on. If a CKEditor
 * upgrade moves or renames those members, these fail rather than the behaviour
 * silently degrading in the browser.
 */
const getEditor = createTestEditor(
  [ParagraphPlugin, LinkPlugin, ResourceLinkUI],
  {
    [RESOURCE_LINK_CONFIG_KEY]: {
      hrefTemplate: "https://example.com/courses/test-site/",
    },
  },
)

describe("ResourceLinkUI", () => {
  it("adds a resource-link decorator to the link config", async () => {
    const editor = await getEditor("")
    const linkConfig = editor.config.get("link")

    expect(linkConfig.decorators.addTargetToExternalLinks.attributes).toEqual({
      class: "resource-link",
    })
    expect(linkConfig.decorators.addTargetToExternalLinks.mode).toBe(
      "automatic",
    )

    await editor.destroy()
  })

  it("exposes the LinkUI action view members it depends on", async () => {
    const editor = await getEditor("")
    const { actionsView } = editor.plugins.get(LinkUI)

    expect(actionsView).toBeTruthy()
    expect(actionsView.editButtonView).toBeTruthy()
    expect(actionsView.previewButtonView).toBeTruthy()
    expect("href" in actionsView).toBe(true)

    await editor.destroy()
  })
})
