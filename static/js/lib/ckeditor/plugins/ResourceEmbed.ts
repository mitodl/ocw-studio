import { pickBy } from "lodash"
import CKEPlugin from "@ckeditor/ckeditor5-core/src/plugin"
import Turndown from "turndown"
import Showdown from "showdown"
import { toWidget } from "@ckeditor/ckeditor5-widget/src/utils"
import { editor } from "@ckeditor/ckeditor5-core"
import Command from "@ckeditor/ckeditor5-core/src/command"

import MarkdownSyntaxPlugin from "./MarkdownSyntaxPlugin"
import { TurndownRule } from "../../../types/ckeditor_markdown"
import {
  CKEDITOR_RESOURCE_UTILS,
  RenderResourceFunc,
  RESOURCE_EMBED,
  RESOURCE_EMBED_COMMAND
} from "./constants"
import { Shortcode, makeHtmlString } from "./util"
import { isNotNil } from "../../../util"

export const RESOURCE_SHORTCODE_REGEX = /{{< resource .*? >}}/g

/**
 * Class for defining Markdown conversion rules for ResourceEmbed
 */
class ResourceMarkdownSyntax extends MarkdownSyntaxPlugin {
  constructor(editor: editor.Editor) {
    super(editor)
  }

  get showdownExtension() {
    return function resourceExtension(): Showdown.ShowdownExtension[] {
      return [
        {
          type:    "lang",
          regex:   RESOURCE_SHORTCODE_REGEX,
          replace: (s: string) => {
            const shortcode = Shortcode.fromString(s)
            const uuid = shortcode.get(0) ?? shortcode.get("uuid")
            const href = shortcode.get("href")
            const hrefUuid = shortcode.get("href_uuid")
            const attrs = {
              "data-uuid":      uuid,
              "data-href":      href,
              "data-href-uuid": hrefUuid
            }
            return makeHtmlString("section", attrs)
          }
        }
      ]
    }
  }

  get turndownRules(): TurndownRule[] {
    return [
      {
        name: "resourceEmbed",
        rule: {
          filter:      "section",
          replacement: (_content: string, node: Turndown.Node): string => {
            if (!(node instanceof HTMLElement)) {
              throw new Error("Node should be HTMLElement")
            }
            const uuid = node.getAttribute("data-uuid")
            if (uuid === null) throw new Error("uuid should not be null")
            const resource = Shortcode.resource(uuid, {
              href:     node.getAttribute("data-href"),
              hrefUuid: node.getAttribute("data-href-uuid")
            })
            return `${resource.toHugo()}\n`
          }
        }
      }
    ]
  }
}

/**
 * A CKEditor Command for inserting a new ResourceEmbed (resourceEmbed)
 * node into the editor.
 */
class InsertResourceEmbedCommand extends Command {
  constructor(editor: editor.Editor) {
    super(editor)
  }

  execute(uuid: string) {
    this.editor.model.change((writer: any) => {
      const embed = writer.createElement(RESOURCE_EMBED, { uuid })
      this.editor.model.insertContent(embed)
    })
  }

  refresh() {
    const model = this.editor.model
    const selection = model.document.selection
    const allowedIn = model.schema.findAllowedParent(
      selection.getFirstPosition(),
      RESOURCE_EMBED
    )
    this.isEnabled = allowedIn !== null
  }
}

/**
 * The main 'editing plugin for ResourceEmbeds. This basically
 * adds the node type to the schema and sets up all the serialization/
 * deserialization rules for it.
 */
class ResourceEmbedEditing extends CKEPlugin {
  constructor(editor: editor.Editor) {
    super(editor)
  }

  init() {
    this._defineSchema()
    this._defineConverters()

    this.editor.commands.add(
      RESOURCE_EMBED_COMMAND,
      new InsertResourceEmbedCommand(this.editor)
    )
  }

  _defineSchema() {
    const schema = this.editor.model.schema

    schema.register(RESOURCE_EMBED, {
      isObject:        true,
      allowWhere:      "$block",
      allowAttributes: ["uuid"]
    })
  }

  _defineConverters() {
    const conversion = this.editor.conversion

    /**
     * convert HTML string to a view element (i.e. ckeditor
     * internal state, *not* to a DOM element)
     */
    conversion.for("upcast").elementToElement({
      view: {
        name: "section"
      },

      model: (viewElement: any, { writer: modelWriter }: any) => {
        return modelWriter.createElement(
          RESOURCE_EMBED,
          pickBy(
            {
              uuid:     viewElement.getAttribute("data-uuid"),
              href:     viewElement.getAttribute("data-href"),
              hrefUuid: viewElement.getAttribute("data-href-uuid")
            },
            isNotNil
          )
        )
      }
    })

    /**
     * converts view element to HTML element for data output
     */
    conversion.for("dataDowncast").elementToElement({
      model: RESOURCE_EMBED,
      view:  (modelElement: any, { writer: viewWriter }: any) => {
        return viewWriter.createEmptyElement(
          "section",
          pickBy(
            {
              "data-uuid":      modelElement.getAttribute("uuid"),
              "data-href":      modelElement.getAttribute("href"),
              "data-href-uuid": modelElement.getAttribute("hrefUuid")
            },
            isNotNil
          )
        )
      }
    })

    const renderResource: RenderResourceFunc = (
      this.editor.config.get(CKEDITOR_RESOURCE_UTILS) ?? {}
    ).renderResource

    /**
     * editingDowncast converts a view element to HTML which is actually shown
     * in the editor for WYSIWYG purposes
     */
    conversion.for("editingDowncast").elementToElement({
      model: RESOURCE_EMBED,
      view:  (modelElement: any, { writer: viewWriter }: any) => {
        const uuid = modelElement.getAttribute("uuid")

        const section = viewWriter.createContainerElement("section", {
          class: "resource-embed"
        })

        const reactWrapper = viewWriter.createRawElement(
          "div",
          {
            class: "resource-react-wrapper"
          },
          function(el: HTMLElement) {
            if (renderResource) {
              renderResource(uuid, el)
            }
          }
        )

        viewWriter.insert(viewWriter.createPositionAt(section, 0), reactWrapper)

        return toWidget(section, viewWriter, { label: "Resources Embed" })
      }
    })
  }
}

/**
 * CKEditor plugin that provides functionality to embed resource records
 * into the editor. These are rendered to Markdown as `{{< resource UUID >}}`
 * shortcodes.
 */
export default class ResourceEmbed extends CKEPlugin {
  static get pluginName(): string {
    return "ResourceEmbed"
  }

  static get requires(): typeof CKEPlugin[] {
    return [ResourceEmbedEditing, ResourceMarkdownSyntax]
  }
}
