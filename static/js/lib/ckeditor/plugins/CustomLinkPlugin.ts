import Plugin from "@ckeditor/ckeditor5-core/src/plugin"
import { Editor } from "@ckeditor/ckeditor5-core"
import LinkUI from "@ckeditor/ckeditor5-link/src/linkui"
import ResourceLinkMarkdownSyntax from "./ResourceLinkMarkdownSyntax"
import ResourceLink from "./ResourceLink"

import { siteApiContentUrl } from "../../urls"
import { getCookie } from "../../api/util"

export default class CustomLinkUI extends Plugin {
  static get pluginName(): string {
    return "CustomLinkUI"
  }

  static get requires() {
    return [LinkUI]
  }

  private get syntax() {
    return this.editor.plugins.get(ResourceLinkMarkdownSyntax)
  }

  init() {
    const linkUI = this.editor.plugins.get(LinkUI)
    const formView = linkUI.formView

    formView.delegate("submit").to(this, "saveLink")

    this.on("saveLink", () => {
      const siteName = formView.element.baseURI.split("/")[4]

      // Access the href value from formView
      const href = formView.urlInputView.fieldView.element.value
      const title = this.editor.model.selection.getSelectedText()

      customLinkHook(this.editor, href, siteName, title)
    })

    console.log("CustomLinkUI Plugin is initialized")
  }
}

async function customLinkHook(
  editor: Editor,
  linkValue: string,
  siteName: string,
  title: string,
) {
  const resourceLink = editor.plugins.get(ResourceLink)

  const payload = {
    type: "external-resource",
    title: title || linkValue,
    metadata: {
      external_url: linkValue,
      license: "https://en.wikipedia.org/wiki/All_rights_reserved",
      has_external_license_warning: false,
      is_broken: "",
      backup_url: "",
    },
  }

  fetch(siteApiContentUrl.param({ name: siteName }).toString(), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFTOKEN": getCookie("csrftoken") || "",
    },
    body: JSON.stringify(payload),
  })
    .then((response) => response.json())
    .then((data) => {
      // Handle successful API response
      resourceLink.createResourceLink(data.text_id, data.title)
    })
}
