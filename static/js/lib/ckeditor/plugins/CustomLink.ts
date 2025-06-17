import Plugin from "@ckeditor/ckeditor5-core/src/plugin"
import { Editor } from "@ckeditor/ckeditor5-core"
import LinkUI from "@ckeditor/ckeditor5-link/src/linkui"
import ResourceLinkMarkdownSyntax from "./ResourceLinkMarkdownSyntax"

import { siteApiContentUrl } from "../../urls"
import { getCookie } from "../../api/util"
import LinkCommand from "@ckeditor/ckeditor5-link/src/linkcommand"
import { Link } from "@ckeditor/ckeditor5-link"
import { WEBSITE_NAME } from "./constants"
import { Range } from "@ckeditor/ckeditor5-engine"
import { DiffItem } from "@ckeditor/ckeditor5-engine/src/model/differ"
import Writer from "@ckeditor/ckeditor5-engine/src/model/writer"

/**
 * CustomLinkCommand extends CKEditor's default LinkCommand to provide automatic
 * external resource creation for external URLs while preserving existing resource links.
 *
 * This command is responsible for:
 * 1. Detecting if a link href is already a resource link (internal) - if so, pass through unchanged
 * 2. For external URLs, automatically create an "external-resource" content item via API
 * 3. Replace the external URL with a resource link that points to the created external resource
 *
 * This allows content editors to simply paste external URLs, and the system automatically
 * creates tracked external resources with licensing information and backup capabilities.
 */
class CustomLinkCommand extends LinkCommand {
  /**
   * Execute the link command with automatic external resource creation.
   *
   * This method intercepts link creation to:
   * 1. Check if the href is already a resource link using ResourceLinkMarkdownSyntax.isResourceLinkHref()
   * 2. If it's a resource link, pass through to the parent LinkCommand unchanged
   * 3. If it's an external URL, create an external resource via API and convert to resource link
   *
   * The title for the external resource is extracted from the current text selection,
   * or defaults to the URL itself (truncated to maxTitle length).
   *
   * @param href - The URL or resource link href to process
   * @param _options - Additional options (currently unused)
   */
  execute(href: string, _options = {}) {
    const syntax = this.editor.plugins.get(ResourceLinkMarkdownSyntax)
    const ranges = this.editor.model.document.selection.getRanges()
    let title = ""
    for (const range of ranges) {
      for (const item of range.getItems()) {
        if (item.is("text") || item.is("textProxy")) {
          title += item.data
        }
      }
    }

    if (syntax.isResourceLinkHref(href)) {
      super.execute(href)
    } else {
      getExternalResource(
        this.editor.config.get(WEBSITE_NAME),
        href,
        title,
      ).then((externalResource) => {
        if (externalResource) {
          updateHref(externalResource, this.editor, (href) =>
            super.execute(href),
          )
        }
      })
    }
  }
}

/**
 * CustomLink Plugin for CKEditor 5
 *
 * PURPOSE:
 * This plugin automatically converts URLs into tracked "external resources"
 * in the OCW Studio content management system. It exists to solve several problems:
 *
 * 1. LICENSE TRACKING: External links need license warnings and rights management
 * 2. LINK ROT PREVENTION: External resources can have backup URLs if originals break
 * 3. CONTENT GOVERNANCE: All external references are catalogued and manageable
 * 4. CONSISTENT LINKING: All links use the same resource link format internally
 *
 * HOW IT WORKS:
 * - Replaces CKEditor's default link command with CustomLinkCommand
 * - When a user creates a link with an external URL, it automatically:
 *   a) Creates an "external-resource" content item via the OCW Studio API
 *   b) Replaces the external URL with a resource link pointing to that item
 *   c) Adds appropriate license warnings based on domain analysis
 * - Existing resource links (internal references) are left unchanged
 * - Monitors document changes to catch paste operations and direct href modifications
 *
 * INTEGRATION:
 * - Requires ResourceLinkMarkdownSyntax plugin for resource link format handling
 * - Uses OCW Studio's content API to create external resource records
 * - Integrates with the site's CSRF protection and authentication
 *
 * CONTENT EDITORS BENEFIT:
 * - Can simply paste external URLs - no manual resource creation needed
 * - All external links get proper license warnings automatically
 * - Centralized management of all external references
 * - Backup URL support for link rot prevention
 */
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

  /**
   * Initialize the CustomLink plugin.
   *
   * This method:
   * 1. Replaces the default 'link' command with CustomLinkCommand
   * 2. Sets up document change monitoring to catch href modifications from:
   *    - Paste operations that bypass the link command
   *    - Direct attribute changes in the editor
   *    - Undo/redo operations that restore external URLs
   *
   * The document change listener ensures that any external URL that appears
   * in the document gets automatically converted to a resource link, regardless
   * of how it was introduced to the content.
   */
  init() {
    this.editor.commands.add("link", new CustomLinkCommand(this.editor))
    console.log("CustomLink Plugin is initialized")

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

  /**
   * Process href attribute changes to convert external URLs to resource links.
   *
   * This method is called when the document change listener detects a linkHref
   * attribute modification. It:
   * 1. Checks if the new href is already a resource link - if so, ignores it
   * 2. For external URLs, creates an external resource via API
   * 3. Updates the href attribute to point to the new resource link
   *
   * This catches cases where external URLs are introduced through:
   * - Copy/paste operations from external sources
   * - Programmatic content changes
   * - Undo operations that restore external URLs
   *
   * @param range - The range where the href attribute was modified
   */
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
          if (externalResource && externalResource.textId) {
            // Update the href attribute with the resourceLink
            this.editor.model.change((writer: Writer) => {
              writer.setAttribute(
                "linkHref",
                this._getResourceLink(externalResource.textId),
                item,
              )
            })
          }
        })
      }
    }
  }

  /**
   * Generate a resource link href from a resource ID.
   *
   * This is a simple wrapper around ResourceLinkMarkdownSyntax.makeResourceLinkHref()
   * that creates properly formatted resource links with the correct URL structure
   * and query parameters needed by the OCW system.
   *
   * @param resourceID - The text_id of the external resource content item
   * @returns A properly formatted resource link href
   */
  _getResourceLink(resourceID: string): string {
    // Example: Appending a query parameter to the original href
    return this.syntax.makeResourceLinkHref(resourceID)
  }
}

/**
 * Create an external resource content item via the OCW Studio API.
 *
 * This function handles the core logic of external resource creation:
 *
 * 1. DOMAIN ANALYSIS: Determines if the URL is external by comparing its hostname
 *    to SETTINGS.sitemapDomain. Same-domain URLs get no license warning.
 *
 * 2. PAYLOAD CONSTRUCTION: Creates an "external-resource" content item with:
 *    - Title: Uses provided title or truncated URL as fallback
 *    - External URL: The original URL for reference
 *    - License: Defaults to "All rights reserved"
 *    - Warning flag: Set based on domain analysis
 *    - Backup URL: Empty by default, can be filled later for link rot prevention
 *
 * 3. API INTERACTION: Posts to the OCW Studio content API with CSRF protection
 *
 * 4. ERROR HANDLING: Gracefully handles network failures and invalid responses
 *
 * @param siteName - The name of the OCW site (from editor config)
 * @param linkValue - The external URL to create a resource for
 * @param title - Optional title for the resource (defaults to URL)
 * @returns Promise resolving to resource info (title, textId) or null on failure
 */
export async function getExternalResource(
  siteName: string,
  linkValue: string,
  title: string,
): Promise<{ title: string; textId: string } | null> {
  let hasWarning = true
  try {
    hasWarning = new URL(linkValue).hostname !== SETTINGS.sitemapDomain
  } catch (error) {
    console.log("Invalid URL provided!")
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
    if (!data.title || !data.text_id) {
      return null
    }
    return { title: data.title, textId: data.text_id }
  } catch (error) {
    console.error("Error updating link:", error)
    return null
  }
}

/**
 * Update the editor content with a resource link after external resource creation.
 *
 * This function handles the final step of link conversion by updating the editor
 * content with the newly created resource link. It supports two scenarios:
 *
 * 1. COLLAPSED SELECTION (no text selected):
 *    - Inserts the resource title as new text with the resource link href
 *    - This happens when users create links without selecting existing text
 *    - Creates clickable link text using the resource title
 *
 * 2. NON-COLLAPSED SELECTION (text is selected):
 *    - Applies the resource link href to the currently selected text
 *    - Preserves the user's chosen link text while updating the destination
 *    - Uses the standard link command to maintain consistent behavior
 *
 * This function ensures that the linking behavior feels natural to content editors
 * while seamlessly converting external URLs to managed resources behind the scenes.
 *
 * @param externalResource - The created resource with title and textId
 * @param editor - The CKEditor instance
 * @param superExecute - The parent LinkCommand.execute method for applying links
 */
export function updateHref(
  externalResource: { title: string; textId: string },
  editor: Editor,
  superExecute: { (customHref: string): void },
) {
  // Handle successful API response
  const { title, textId } = externalResource

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
        title,
        {
          linkHref: syntax(textId),
        },
        insertPosition,
      )
    })
  } else {
    /**
     * If the selection is not collapsed, we apply the original link command to the
     * selected text.
     */
    superExecute(syntax(textId))
  }
}
