import { Plugin } from "@ckeditor/ckeditor5-core"
import ResourceLinkMarkdownSyntax from "./ResourceLinkMarkdownSyntax"
import ResourceLinkUI from "./ResourceLinkUI"

/**
 * Resource links are a markdown shortcode (custom syntax) for linking to
 * resources by UUID.
 *
 * The syntax is
 * ```md
 * {{% resource_link "{uuid}" "{title}" "{optional_suffix}" %}}
 * ```
 * where
 *  - {uuid} specifies the linked resource
 *  - {title} is the link title
 *  - {optional_suffix} is appended to the final link URL when markdown
 *    is converted to *published* HTML.
 *
 *    *This is currently used only by legacy content for linking to document
 *    fragments. There is no UI for adding this parameter to a resource link.*
 *
 * This Plugin provides support to CKEditor for understanding resource links.
 *
 * The general approach is:
 *  1. Convert the Markdown to <a> tags, with an href that encodes shortcode
 *     parameters as query parameters.
 *
 *     The "front" of the href specifies a preview of the resource that CKEditor
 *     shows as the link target. For example, if the UUID specifies "Calendar",
 *     the preview might be the Studio page for that resource.
 *  2. Use CKEditor's regular link plugin for displaying and editing the link
 *     text.
 *
 *     *The behavior is modified slightly via `ResourceLinkUI`, to prevent
 *     things like manually editing the resource link anchor's href.*
 */
export default class ResourceLink extends Plugin {
  static get pluginName() {
    return "ResourceLink"
  }

  static get requires() {
    return [ResourceLinkUI, ResourceLinkMarkdownSyntax]
  }

  private get syntax() {
    return this.editor.plugins.get(ResourceLinkMarkdownSyntax)
  }

  /**
   * Create a new resource link.
   *
   * If the current editor selection is "collapsed" (no text is highlighted),
   * insert a new resource link with text equal to the resource title.
   *
   * If there is text highlighted, apply the link to the highlighted text.
   */
  createResourceLink = (uuid: string, title: string) => {
    if (this.editor.model.document.selection.isCollapsed) {
      /**
       * If the selection is collapsed, nothing is highlighted. See
       *  - [selection.isCollapsed](https://ckeditor.com/docs/ckeditor5/latest/api/module_engine_view_selection-Selection.html#member-isCollapsed)
       *  - [range.isCollapsed](https://ckeditor.com/docs/ckeditor5/latest/api/module_engine_model_range-Range.html#member-isCollapsed)
       */
      this.editor.model.change(writer => {
        const insertPosition =
          this.editor.model.document.selection.getFirstPosition()
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
      this.editor.execute("link", this.syntax.makeResourceLinkHref(uuid))
    }
  }
}
