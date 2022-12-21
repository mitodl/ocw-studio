import { ShowdownExtension } from "showdown"
import CKPlugin from "@ckeditor/ckeditor5-core/src/plugin"
import { Editor } from "@ckeditor/ckeditor5-core"

import MarkdownSyntaxPlugin from "./MarkdownSyntaxPlugin"
import { TurndownRule } from "../../../types/ckeditor_markdown"
import { LEGACY_SHORTCODES } from "./constants"
import { Shortcode } from "./util"

const shortcodeClass = (shortcode: string) => `legacy-shortcode-${shortcode}`

const DATA_ISCLOSING = "data-isclosing"
const DATA_ARGUMENTS = "data-arguments"

class LegacyShortcodeSyntax extends MarkdownSyntaxPlugin {
  static get pluginName(): string {
    return "LegacyShortcodeSyntax"
  }

  get showdownExtension() {
    return function legacyShortcodeExtension(): ShowdownExtension[] {
      const nameRegex = new RegExp(LEGACY_SHORTCODES.join("|"))
      return [
        {
          type:    "lang",
          /**
           * It's important that there's a single regex for all the legacy
           * shortcodes, rather than one per shortcode. Otherwise the order of
           * the replacements is important.
           *
           * For example, image-gallery-item and sub are both legacy shortcodes
           * and sometimes they are used together:
           *  {{< image-gallery-item ... "H{{< sub 2 >}}O" >}}
           * If separate regexes are used, then image-gallery-item would need to
           * come before sub so that the sub-replacement is not used on the above
           * example.
           */
          regex:   Shortcode.regex(nameRegex, false),
          replace: (stringMatch: string) => {
            const shortcode = Shortcode.fromString(stringMatch)
            const { isClosing } = shortcode
            const params = shortcode.params.map(p => p.toHugo()).join(" ")
            const tag = `<span ${DATA_ISCLOSING}="${isClosing}" ${
              params ? `${DATA_ARGUMENTS}="${encodeURIComponent(params)}"` : ""
            } class="${shortcodeClass(shortcode.name)}"></span>`

            return tag
          }
        }
      ]
    }
  }

  get turndownRules(): TurndownRule[] {
    return LEGACY_SHORTCODES.map(shortcode => ({
      name: `LegacyShortcodeSyntax-${shortcode}`,
      rule: {
        filter: node => {
          return (
            node.nodeName === "SPAN" &&
            node.className === shortcodeClass(shortcode)
          )
        },
        replacement: (_content: string, node: any): string => {
          const isClosingTag = JSON.parse(node.getAttribute(DATA_ISCLOSING))
          const rawShortcodeArgs = node.getAttribute(DATA_ARGUMENTS)

          return `{{< ${isClosingTag ? "/" : ""}${shortcode} ${
            rawShortcodeArgs !== undefined && rawShortcodeArgs !== null ?
              `${decodeURIComponent(rawShortcodeArgs)} ` :
              ""
          }>}}`
        }
      }
    }))
  }
}

const shortcodeModelName = (shortcode: string) =>
  `legacy-shortcode-${shortcode}`

class LegacyShortcodeEditing extends CKPlugin {
  static get pluginName(): string {
    return "LegacyShortcodeEditing"
  }

  constructor(editor: Editor) {
    super(editor)
  }

  init() {
    this._defineSchema()
    this._defineConverters()
  }

  _defineSchema() {
    const schema = this.editor.model.schema

    LEGACY_SHORTCODES.map(shortcode => {
      schema.register(`legacy-shortcode-${shortcode}`, {
        isInline:        true,
        allowWhere:      "$text",
        isObject:        true,
        allowAttributes: ["isClosing", "arguments"]
      })
    })
  }

  _defineConverters() {
    const conversion = this.editor.conversion

    LEGACY_SHORTCODES.map(shortcode => {
      /**
       * convert HTML string to a view element (i.e. ckeditor
       * internal state, *not* to a DOM element)
       */
      conversion.for("upcast").elementToElement({
        view: {
          name:    "span",
          classes: [shortcodeClass(shortcode)]
        },
        model: (viewElement: any, { writer: modelWriter }: any) => {
          const attrs: any = {
            isClosing: viewElement.getAttribute(DATA_ISCLOSING)
          }

          const dataArguments = viewElement.getAttribute(DATA_ARGUMENTS)
          if (dataArguments) {
            attrs.arguments = dataArguments
          }

          return modelWriter.createElement(shortcodeModelName(shortcode), attrs)
        }
      })

      /**
       * converts view element to HTML element for data output
       */
      conversion.for("dataDowncast").elementToElement({
        model: shortcodeModelName(shortcode),
        view:  (modelElement: any, { writer: viewWriter }: any) => {
          const attrs: any = {
            [DATA_ISCLOSING]: modelElement.getAttribute("isClosing"),
            class:            shortcodeClass(shortcode)
          }

          const dataArguments = modelElement.getAttribute("arguments")
          if (dataArguments) {
            attrs[DATA_ARGUMENTS] = dataArguments
          }

          return viewWriter.createRawElement("span", attrs, function(
            el: HTMLElement
          ) {
            el.innerHTML = shortcode
          })
        }
      })

      /**
       * editingDowncast converts a view element to HTML which is actually shown
       * in the editor for WYSIWYG purposes
       */
      conversion.for("editingDowncast").elementToElement({
        model: shortcodeModelName(shortcode),

        view: (modelElement: any, { writer: viewWriter }: any) => {
          const isClosing = modelElement.getAttribute("isClosing")

          const el = viewWriter.createRawElement(
            "span",
            {
              class: `${shortcodeClass(shortcode)} legacy-shortcode`
            },
            function(el: HTMLElement) {
              el.innerHTML =
                isClosing.trim() === "true" ? `/${shortcode}` : `${shortcode}`
            }
          )

          return el
        }
      })
    })
  }
}

export default class LegacyShortcodes extends CKPlugin {
  static get requires(): typeof CKPlugin[] {
    return [LegacyShortcodeEditing, LegacyShortcodeSyntax]
  }
}
