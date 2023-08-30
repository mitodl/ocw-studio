import { Editor } from "@ckeditor/ckeditor5-core"
import { Plugin } from "@ckeditor/ckeditor5-core"
import { LinkUI } from "@ckeditor/ckeditor5-link"
import { ContextualBalloon } from "@ckeditor/ckeditor5-ui"
import ResourceLinkMarkdownSyntax from "./ResourceLinkMarkdownSyntax"

const RESOURCE_LINK_CLASS = "resource-link"

/**
 * This plugin modifies the LinkUI plugin to disable the "Edit" button for
 * resource links and apply a custom class to all resource links.
 */
export default class ResourceLinkUI extends Plugin {
  static get pluginName() {
    return "ResourceLinkUI"
  }

  static get requires() {
    return [LinkUI, ContextualBalloon, ResourceLinkMarkdownSyntax]
  }

  private get syntax() {
    return this.editor.plugins.get(ResourceLinkMarkdownSyntax)
  }
  private get linkUI() {
    return this.editor.plugins.get(LinkUI)
  }
  private get contextualBalloon() {
    return this.editor.plugins.get(ContextualBalloon)
  }

  private originalEditinkLabel!: string

  constructor(editor: Editor) {
    super(editor)
    this.decorateWithClass()
  }

  init() {
    this.contextualBalloon.on("change:visibleView", () => {
      if (this.contextualBalloon.visibleView === this.linkUI.actionsView) {
        if (this.originalEditinkLabel === undefined) {
          this.originalEditinkLabel =
            this.linkUI.actionsView.editButtonView.label
        }
        this.modifyLinkUI()
      }
    })
  }

  private modifyLinkUI() {
    const actionsView = this.editor.plugins.get(LinkUI).actionsView
    // @ts-expect-error href is documented but not in TS yet
    const href: string = actionsView.href
    if (this.syntax.isResourceLinkHref(href)) {
      actionsView.editButtonView.label = ""
      actionsView.editButtonView.isEnabled = false
      actionsView.editButtonView.isVisible = false
      const previewEl = actionsView.previewButtonView.element
      if (previewEl instanceof HTMLAnchorElement) {
        previewEl.href = this.syntax.makePreviewHref(href)
      }
      actionsView.previewButtonView.element
    } else {
      actionsView.editButtonView.label = this.originalEditinkLabel
      actionsView.editButtonView.isEnabled = true
      actionsView.editButtonView.isVisible = true
    }
  }

  /**
   * Adds a class to all links that ResourceLinkMarkdownSyntax determines are
   * resource links.
   */
  private decorateWithClass() {
    const linkConfig = this.editor.config.get("link")
    this.editor.config.set("link", {
      ...linkConfig,
      decorators: {
        ...linkConfig.decorators,
        addTargetToExternalLinks: {
          mode: "automatic",
          callback: (url?: string) => this.syntax.isResourceLinkHref(url),
          attributes: {
            class: RESOURCE_LINK_CLASS,
          },
        },
      },
    })
  }
}
