import { Editor } from "@ckeditor/ckeditor5-core"
import { Plugin } from "@ckeditor/ckeditor5-core"
import { LinkUI } from "@ckeditor/ckeditor5-link"
import { ContextualBalloon } from "@ckeditor/ckeditor5-ui"
import ResourceLinkMarkdownSyntax from "./ResourceLinkMarkdownSyntax"

export default class ResourceLink extends Plugin {
  static get pluginName() {
    return "ResourceLink"
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
          this.originalEditinkLabel = this.linkUI.actionsView.editButtonView.label
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
      const previewEl = actionsView.previewButtonView.element
      if (previewEl instanceof HTMLAnchorElement) {
        previewEl.href = this.syntax.removeResourceLinkQueryParams(href)
      }
      actionsView.previewButtonView.element
    } else {
      actionsView.editButtonView.label = this.originalEditinkLabel
      actionsView.editButtonView.isEnabled = true
    }
  }

  insertResourceLink = (uuid: string, title: string) => {
    if (this.editor.model.document.selection.isCollapsed) {
      /**
       * If the selection is collapsed, nothing is highlighted. See
       *  - [selection.isCollapsed](https://ckeditor.com/docs/ckeditor5/latest/api/module_engine_view_selection-Selection.html#member-isCollapsed)
       *  - [range.isCollapsed](https://ckeditor.com/docs/ckeditor5/latest/api/module_engine_model_range-Range.html#member-isCollapsed)
       *
       * If nothing is highlighted, we want to insert new text equal to the
       * resource title, with an href pointing at the resource.
       */
      this.editor.model.change(writer => {
        const insertPosition = this.editor.model.document.selection.getFirstPosition()
        writer.insertText(
          title,
          {
            linkHref: this.syntax.makeResourceLinkHref(uuid)
          },
          insertPosition
        )
      })
    } else {
      /**
       * If the selection is not collapsed, we apply the link to the selected
       * text.
       */
      this.editor.execute("link", {
        linkHref: this.syntax.makeResourceLinkHref(uuid)
      })
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
          mode:       "automatic",
          callback:   (url?: string) => this.syntax.isResourceLinkHref(url),
          attributes: {
            class: "resource-link"
          }
        }
      }
    })
  }
}
