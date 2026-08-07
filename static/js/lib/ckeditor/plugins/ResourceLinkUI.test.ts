import LinkPlugin from "@ckeditor/ckeditor5-link/src/link"
import { LinkUI } from "@ckeditor/ckeditor5-link"
import { ContextualBalloon } from "@ckeditor/ckeditor5-ui"
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
    const linkUI = editor.plugins.get(LinkUI)

    // LinkUI builds its views lazily, the first time the balloon needs them,
    // so force that here before asserting on the shape ResourceLinkUI reads.
    expect(linkUI.actionsView).toBeNull()
    ;(linkUI as unknown as { _createViews(): void })._createViews()

    const actionsView = linkUI.actionsView!

    expect(actionsView).toBeTruthy()
    expect(actionsView.editButtonView).toBeTruthy()
    expect(actionsView.previewButtonView).toBeTruthy()
    expect("href" in actionsView).toBe(true)

    await editor.destroy()
  })

  it("ignores balloon changes while the link actions view is still null", async () => {
    const editor = await getEditor("")
    const balloon = editor.plugins.get(ContextualBalloon)

    // Both of these are null before any link balloon has been opened. A bare
    // identity check between them reads as true, which would send
    // ResourceLinkUI on to dereference the null actions view.
    expect(editor.plugins.get(LinkUI).actionsView).toBeNull()
    expect(balloon.visibleView).toBeNull()

    expect(() => balloon.fire("change:visibleView")).not.toThrow()

    await editor.destroy()
  })
})
