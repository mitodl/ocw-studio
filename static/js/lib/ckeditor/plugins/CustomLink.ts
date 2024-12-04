import Plugin from "@ckeditor/ckeditor5-core/src/plugin"
import { Editor } from "@ckeditor/ckeditor5-core"
import LinkUI from "@ckeditor/ckeditor5-link/src/linkui"
import ResourceLinkMarkdownSyntax from "./ResourceLinkMarkdownSyntax"

import { siteApiContentUrl } from "../../urls"
import { getCookie } from "../../api/util"
import LinkCommand from "@ckeditor/ckeditor5-link/src/linkcommand"
import UnlinkCommand from "@ckeditor/ckeditor5-link/src/unlinkcommand"
import { Link } from "@ckeditor/ckeditor5-link"
import { REFERENCED_CONTENT, WEBSITE_NAME } from "./constants"
import { Range } from "@ckeditor/ckeditor5-engine"
import { DiffItem } from "@ckeditor/ckeditor5-engine/src/model/differ"
import Writer from "@ckeditor/ckeditor5-engine/src/model/writer"
class CustomLinkCommand extends LinkCommand {
  execute(href: string, _options = {}) {
    const ranges = this.editor.model.document.selection.getRanges()
    let title = ""
    for (const range of ranges) {
      for (const item of range.getItems()) {
        if (item.is("text") || item.is("textProxy")) {
          title += item.data
        }
      }
    }

    getExternalResource(this.editor.config.get(WEBSITE_NAME), href, title).then(
      (externalResource) => {
        if (externalResource) {
          updateHref(externalResource, this.editor, (href) =>
            super.execute(href),
          )

          // Add the updated Resource Link ID in references context
          const referencedContent = this.editor.config.get(REFERENCED_CONTENT)
          referencedContent.add(externalResource.textId)
        }
      },
    )
  }
}

class CustomUnlinkCommand extends UnlinkCommand {
  execute() {
    // Add the updated Resource Link ID in references context
    const href = this.editor.model.document.selection.getAttribute("linkHref")
    if (href) {
      const resourceID = this.editor.plugins
        .get(ResourceLinkMarkdownSyntax)
        .getResourceLinkID(String(href))
      if (resourceID) {
        const referencedContent = this.editor.config.get(REFERENCED_CONTENT)
        referencedContent.remove(resourceID)
      }
    }

    // Call the original unlink logic
    super.execute()
  }
}

export default class CustomLink extends Plugin {
  static get pluginName(): string {
    return "CustomLink"
  }

  static get requires() {
    return [Link, LinkUI, ResourceLinkMarkdownSyntax]
  }

  private get syntax() {
    return this.editor.plugins.get(ResourceLinkMarkdownSyntax)
  }

  init() {
    this.editor.commands.add("link", new CustomLinkCommand(this.editor))
    this.editor.commands.add("unlink", new CustomUnlinkCommand(this.editor))

    // Intercept change in document
    this.editor.model.document.on("change:data", () => {
      const changes = Array.from(this.editor.model.document.differ.getChanges())

      for (const entry of changes as [DiffItem]) {
        if (entry.type === "attribute" && entry.attributeKey === "linkHref") {
          this._modifyHref(entry.range)
        }
      }
    })
  }

  // Custom method to modify the href
  _modifyHref(range: Range) {
    // Get the link element in the given range
    for (const item of range.getItems()) {
      // Modify href only if its not a ResourceLink
      if (
        item.hasAttribute("linkHref") &&
        !this.syntax.isResourceLinkHref(item.getAttribute("linkHref"))
      ) {
        const originalHref = item.getAttribute("linkHref")

        getExternalResource(
          this.editor.config.get(WEBSITE_NAME),
          String(originalHref),
          "",
        ).then((externalResource) => {
          if (externalResource) {
            // Update the href attribute with the resourceLink
            this.editor.model.change((writer: Writer) => {
              writer.setAttribute(
                "linkHref",
                this._getResourceLink(externalResource.textId || ""),
                item,
              )
            })

            // Add the updated Resource Link ID in references context
            const referencedContent = this.editor.config.get(REFERENCED_CONTENT)
            referencedContent.add(externalResource.textId)
          }
        })
      }
    }
  }

  // This function can contain your custom logic to generate a new href
  _getResourceLink(resourceID: string): string {
    // Example: Appending a query parameter to the original href
    return this.syntax.makeResourceLinkHref(resourceID)
  }
}

async function getExternalResource(
  siteName: string,
  linkValue: string,
  title: string,
): Promise<{ title: string; textId: string } | null> {
  let hasWarning = true
  try {
    hasWarning = new URL(linkValue).hostname !== SETTINGS.sitemapDomain
  } catch (error) {
    //Invalid URL provided! Ignored as this could be due to a missing scheme.
  }

  const payload = {
    type: "external-resource",
    title: title || linkValue.slice(0, SETTINGS.maxTitle),
    metadata: {
      external_url: linkValue,
      license: "https://en.wikipedia.org/wiki/All_rights_reserved",
      has_external_license_warning: hasWarning,
      is_broken: "",
      backup_url: "",
    },
  }

  try {
    const response = await fetch(
      siteApiContentUrl.param({ name: siteName }).toString(),
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFTOKEN": getCookie("csrftoken") || "",
        },
        body: JSON.stringify(payload),
      },
    )

    const data = await response.json()
    return { title: data.title, textId: data.text_id }
  } catch (error) {
    console.error("Error updating link:", error)
    return null
  }
}

function updateHref(
  externalResource: { title?: string; textId?: string },
  editor: Editor,
  superExecute: { (customHref: string): void },
) {
  // Handle successful API response

  const syntax = editor.plugins.get(
    ResourceLinkMarkdownSyntax,
  ).makeResourceLinkHref

  if (editor.model.document.selection.isCollapsed) {
    /**
     * If the selection is collapsed, nothing is highlighted. See
     *  - [selection.isCollapsed](https://ckeditor.com/docs/ckeditor5/latest/api/module_engine_view_selection-Selection.html#member-isCollapsed)
     *  - [range.isCollapsed](https://ckeditor.com/docs/ckeditor5/latest/api/module_engine_model_range-Range.html#member-isCollapsed)
     */
    editor.model.change((writer) => {
      const insertPosition = editor.model.document.selection.getFirstPosition()
      writer.insertText(
        externalResource.title || "",
        {
          linkHref: syntax(externalResource.textId || ""),
        },
        insertPosition,
      )
    })
  } else {
    /**
     * If the selection is not collapsed, we apply the original link command to the
     * selected text.
     */
    superExecute(syntax(externalResource.textId || ""))
  }
}
