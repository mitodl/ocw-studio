import { ShowdownExtension } from "showdown"
import Plugin from "@ckeditor/ckeditor5-core/src/plugin"
import { editor } from "@ckeditor/ckeditor5-core"

import MarkdownSyntaxPlugin from "./MarkdownSyntaxPlugin"
import { TurndownRule } from "../../../types/ckeditor_markdown"
import { LEGACY_SHORTCODES } from "./constants"
import { replaceShortcodes, Shortcode } from "./util"

const shortcodeClass = (shortcode: string) => `legacy-shortcode-${shortcode}`

const DATA_ISCLOSING = "data-isclosing"
const DATA_ARGUMENTS = "data-arguments"

class LegacyShortcodeSyntax extends MarkdownSyntaxPlugin {
  static get pluginName(): string {
    return "LegacyShortcodeSyntax"
  }

  get showdownExtension() {
    return (): ShowdownExtension[] => [
      {
        type:   "lang",
        filter: text => {
          const replacer = (shortcode: Shortcode, originalText: string) => {
            if (LEGACY_SHORTCODES.includes(shortcode.name)) {
              const paramsText = shortcode.params.map(p => p.toHugo()).join(" ")
              const tag = `<span ${DATA_ISCLOSING}="${shortcode.isClosing}" ${
                shortcode.params.length > 0 ?
                  `${DATA_ARGUMENTS}="${encodeURIComponent(paramsText)}"` :
                  ""
              } class="${shortcodeClass(shortcode.name)}"></span>`
              return tag
            }
            return originalText
          }
          return replaceShortcodes(text, replacer)
        }
      }
    ]
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

class LegacyShortcodeEditing extends Plugin {
  static get pluginName(): string {
    return "LegacyShortcodeEditing"
  }

  constructor(editor: editor.Editor) {
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

export default class LegacyShortcodes extends Plugin {
  static get requires(): Plugin[] {
    return [
      // @ts-ignore
      LegacyShortcodeEditing,
      // @ts-ignore
      LegacyShortcodeSyntax
    ]
  }
}
