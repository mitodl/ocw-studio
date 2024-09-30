import Plugin from "@ckeditor/ckeditor5-core/src/plugin"
import { Editor } from "@ckeditor/ckeditor5-core"
import LinkUI from "@ckeditor/ckeditor5-link/src/linkui"
import ResourceLinkMarkdownSyntax from "./ResourceLinkMarkdownSyntax"

import { siteApiContentUrl } from "../../urls"
import { getCookie } from "../../api/util"
import LinkCommand from "@ckeditor/ckeditor5-link/src/linkcommand"
import { Link } from "@ckeditor/ckeditor5-link"
import { WEBSITE_NAME } from "./constants"

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
    customLinkHook(this.editor, href, title, (customHref: string) =>
      super.execute(customHref),
    )
  }
}

export default class CustomLink extends Plugin {
  static get pluginName(): string {
    return "CustomLink"
  }

  static get requires() {
    return [Link, LinkUI]
  }

  init() {
    this.editor.commands.add("link", new CustomLinkCommand(this.editor))
    console.log("CustomLink Plugin is initialized")
  }
}

async function customLinkHook(
  editor: Editor,
  linkValue: string,
  title: string,
  superExecute: { (customHref: string): void },
) {
  const payload = {
    type: "external-resource",
    title: title || linkValue,
    metadata: {
      external_url: linkValue,
      license: "https://en.wikipedia.org/wiki/All_rights_reserved",
      has_external_license_warning: true,
      is_broken: "",
      backup_url: "",
    },
  }

  console.log("payload", payload)

  fetch(
    siteApiContentUrl
      .param({ name: editor.config.get(WEBSITE_NAME) })
      .toString(),
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFTOKEN": getCookie("csrftoken") || "",
      },
      body: JSON.stringify(payload),
    },
  )
    .then((response) => response.json())
    .then((data) => {
      // Handle successful API response
      console.log("response", data)

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
          const insertPosition =
            editor.model.document.selection.getFirstPosition()
          console.log("insert position", insertPosition)
          writer.insertText(
            data.title,
            {
              linkHref: syntax(data.text_id),
            },
            insertPosition,
          )
        })
      } else {
        /**
         * If the selection is not collapsed, we apply the original link command to the
         * selected text.
         */
        superExecute(syntax(data.text_id))
      }

      const actionsView = editor.plugins.get(LinkUI).actionsView

      actionsView.editButtonView.label = ""
      actionsView.editButtonView.isEnabled = false
      actionsView.editButtonView.isVisible = false
    })
}
