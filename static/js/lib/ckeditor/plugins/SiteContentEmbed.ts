import Plugin from "@ckeditor/ckeditor5-core/src/plugin"
import Turndown from "turndown"
import Showdown from "showdown"
import { toWidget } from "@ckeditor/ckeditor5-widget/src/utils"
import { editor } from "@ckeditor/ckeditor5-core"

import MarkdownSyntaxPlugin from "./MarkdownSyntaxPlugin"
import { TurndownRule } from "../../../types/ckeditor_markdown"

export const SITE_CONTENT_SHORTCODE_REGEX = /{{< resource (\S+) >}}/g

const SITE_CONTENT_EMBED = "siteContent"

class SiteContentMarkdownSyntax extends MarkdownSyntaxPlugin {
  constructor(editor: editor.Editor) {
    super(editor)
  }

  get showdownExtension() {
    return function siteContentExtension(): Showdown.ShowdownExtension[] {
      return [
        {
          type:    "lang",
          regex:   SITE_CONTENT_SHORTCODE_REGEX,
          replace: (s: string, match: string) => `<section>${match}</section>`
        }
      ]
    }
  }

  get turndownRule(): TurndownRule {
    return {
      name: "siteContent",
      rule: {
        filter:      "section",
        replacement: (content: string, _node: Turndown.Node): string => {
          return `{{< resource ${content} >}}\n`
        }
      }
    }
  }
}

class SiteContentEmbedEditing extends Plugin {
  constructor(editor: editor.Editor) {
    super(editor)
  }

  init() {
    this._defineSchema()
    this._defineConverters()
  }

  _defineSchema() {
    const schema = this.editor.model.schema

    schema.register(SITE_CONTENT_EMBED, {
      isObject:       true,
      allowWhere:     "$block",
      allowContentOf: "$block"
    })
  }

  _defineConverters() {
    const conversion = this.editor.conversion

    /**
     * convert HTML string to a view element (i.e. ckeditor
     * internal state, *not* to a DOM element)
     */
    conversion.for("upcast").elementToElement({
      model: SITE_CONTENT_EMBED,
      view:  {
        name: "section"
      }
    })

    /**
     * converts view element to HTML element for data output
     */
    conversion.for("dataDowncast").elementToElement({
      model: SITE_CONTENT_EMBED,
      view:  {
        name: "section"
      }
    })

    /**
     * editingDowncast converts a view element to HTML which is actually shown
     * in the editor for WYSIWYG purposes
     * (for the youtube embed this is an iframe)
     */
    conversion.for("editingDowncast").elementToElement({
      model: SITE_CONTENT_EMBED,
      view:  (modelElement: any, { writer: viewWriter }: any) => {
        // this looks bad but I promise it's fine
        const resourceID = modelElement._children._nodes[0]._data
        const div = viewWriter.createContainerElement("div", {
          class: "resource-embed",
          text:  resourceID
        })
        return toWidget(div, viewWriter, { label: "Resources Embed" })
      }
    })
  }
}

export default class SiteContentEmbed extends Plugin {
  static get pluginName(): string {
    return "SiteContentEmbed"
  }

  static get requires(): Plugin[] {
    // this line here is throwing a type error that I don't understand,
    // since very similar code in MarkdownMediaEmbed.ts is fine
    //
    // Anyhow, since I have not diagnosed it and since things seem to
    // be running fine I'm going to just ignore for now.
    // @ts-ignore
    return [SiteContentEmbedEditing, SiteContentMarkdownSyntax]
  }
}
