import Plugin from "@ckeditor/ckeditor5-core/src/plugin"
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
  RESOURCE_LINK,
  RESOURCE_LINK_COMMAND
} from "./constants"

export const RESOURCE_LINK_SHORTCODE_REGEX = /{{< resource_link (\S+) >}}/g

const RESOURCE_LINK_CKEDITOR_CLASS = "resource-link"

/**
 * Class for defining Markdown conversion rules for ResourceEmbed
 */
class ResourceLinkMarkdownSyntax extends MarkdownSyntaxPlugin {
  constructor(editor: editor.Editor) {
    super(editor)
  }

  get showdownExtension() {
    return function resourceExtension(): Showdown.ShowdownExtension[] {
      return [
        {
          type:    "lang",
          regex:   RESOURCE_LINK_SHORTCODE_REGEX,
          replace: (_s: string, match: string) => {
            return `<span class="${RESOURCE_LINK_CKEDITOR_CLASS}" data-uuid="${match}"></span>`
          }
        }
      ]
    }
  }

  get turndownRule(): TurndownRule {
    return {
      name: RESOURCE_LINK,
      rule: {
        // TODO fix filter here
        filter:      "span",
        replacement: (_content: string, node: Turndown.Node): string => {
          // @ts-ignore
          const uuid = node.getAttribute("data-uuid")
          return `{{< resource_link ${uuid} >}}`
        }
      }
    }
  }
}

/**
 * A CKEditor Command for inserting a new ResourceEmbed (resourceEmbed)
 * node into the editor.
 */
class InsertResourceLinkCommand extends Command {
  constructor(editor: editor.Editor) {
    super(editor)
  }

  execute(uuid: string) {
    this.editor.model.change((writer: any) => {
      const link = writer.createElement(RESOURCE_LINK, { uuid })
      this.editor.model.insertContent(link)
    })
  }

  refresh() {
    const model = this.editor.model
    const selection = model.document.selection
    const allowedIn = model.schema.findAllowedParent(
      selection.getFirstPosition(),
      RESOURCE_LINK
    )
    this.isEnabled = allowedIn !== null
  }
}

/**
 * The main 'editing' plugin for Resource Links. This basically
 * adds the node type to the schema and sets up all the serialization/
 * deserialization rules for it.
 */
class ResourceLinkEditing extends Plugin {
  constructor(editor: editor.Editor) {
    super(editor)
  }

  init() {
    this._defineSchema()
    this._defineConverters()

    this.editor.commands.add(
      RESOURCE_LINK_COMMAND,
      new InsertResourceLinkCommand(this.editor)
    )
  }

  _defineSchema() {
    const schema = this.editor.model.schema

    schema.register(RESOURCE_LINK, {
      isObject:        true,
      isInline:        true,
      isBlock:         false,
      allowIn:         ["$root", "$block"],
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
        name:  "span",
        class: RESOURCE_LINK_CKEDITOR_CLASS
      },

      model: (viewElement: any, { writer: modelWriter }: any) => {
        return modelWriter.createElement(RESOURCE_LINK, {
          uuid: viewElement.getAttribute("data-uuid")
        })
      }
    })

    /**
     * converts view element to HTML element for data output
     */
    conversion.for("dataDowncast").elementToElement({
      model: RESOURCE_LINK,
      view:  (modelElement: any, { writer: viewWriter }: any) => {
        return viewWriter.createEmptyElement("span", {
          "data-uuid": modelElement.getAttribute("uuid"),
          class:       RESOURCE_LINK_CKEDITOR_CLASS
        })
      }
    })

    const renderResource: RenderResourceFunc = (
      this.editor.config.get(CKEDITOR_RESOURCE_UTILS) ?? {}
    ).renderResource

    /**
     * editingDowncast converts a view element to HTML which is actually shown
     * in the editor for WYSIWYG purposes
     * (for the youtube embed this is an iframe)
     */
    conversion.for("editingDowncast").elementToElement({
      model: RESOURCE_LINK,
      view:  (modelElement: any, { writer: viewWriter }: any) => {
        const uuid = modelElement.getAttribute("uuid")

        const span = viewWriter.createContainerElement("span", {
          class: RESOURCE_LINK_CKEDITOR_CLASS
        })

        const reactWrapper = viewWriter.createRawElement(
          "span",
          {
            class: "resource-react-wrapper"
          },
          function(el: HTMLElement) {
            if (renderResource) {
              renderResource(uuid, el, RESOURCE_LINK)
            }
          }
        )

        viewWriter.insert(viewWriter.createPositionAt(span, 0), reactWrapper)

        return toWidget(span, viewWriter, { label: "Resource Link" })
      }
    })
  }
}

/**
 * CKEditor plugin that provides functionality to link to resource records
 * in the editor. These are rendered to Markdown as `{{< resource_link UUID >}}`
 * shortcodes.
 */
export default class ResourceLink extends Plugin {
  static get pluginName(): string {
    return "ResourceLink"
  }

  static get requires(): Plugin[] {
    // this return value here is throwing a type error that I don't understand,
    // since very similar code in MarkdownMediaEmbed.ts is fine
    //
    // Anyhow, since I have not diagnosed it and since things seem to
    // be running fine I'm going to just ignore for now.
    return [
      // @ts-ignore
      ResourceLinkEditing,
      // @ts-ignore
      ResourceLinkMarkdownSyntax
    ]
  }
}
