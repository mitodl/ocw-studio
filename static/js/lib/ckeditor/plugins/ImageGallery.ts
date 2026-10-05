import CKEPlugin from "@ckeditor/ckeditor5-core/src/plugin"
import Command from "@ckeditor/ckeditor5-core/src/command"
import Showdown from "showdown"
import Turndown from "turndown"
import { Editor } from "@ckeditor/ckeditor5-core"
import { toWidget } from "@ckeditor/ckeditor5-widget/src/utils"
import ButtonView from "@ckeditor/ckeditor5-ui/src/button/buttonview"
import { getCode, parseKeystroke } from "@ckeditor/ckeditor5-utils"

import MarkdownSyntaxPlugin from "./MarkdownSyntaxPlugin"
import { TurndownRule } from "../../../types/ckeditor_markdown"
import {
  ADD_IMAGE_GALLERY,
  CKEDITOR_RESOURCE_UTILS,
  IMAGE_GALLERY,
  IMAGE_GALLERY_COMMAND,
  ImageGalleryHandle,
  RenderGalleryFunc,
} from "./constants"

const GALLERY_CLASS = "image-gallery"
const DATA_PARAMS = "data-params"
const DATA_ITEMS = "data-items"
const PARAMS = "params"
const ITEMS = "items"

/** The keystrokes CKEditor's Undo plugin binds, and their commands. */
const HISTORY_KEYSTROKES = new Map([
  [parseKeystroke("Ctrl+Z"), "undo"],
  [parseKeystroke("Ctrl+Y"), "redo"],
  [parseKeystroke("Ctrl+Shift+Z"), "redo"],
])

/**
 * A shortcode's raw param text: everything up to the closing `>}}`, with each
 * double-quoted value consumed whole, so a `>}}` inside one cannot end the tag.
 * Real captions nest shortcodes, e.g. `text="Pyrite: FeS{{< sub 2 >}}"`.
 */
const RAW_PARAMS = String.raw`((?:[^"]|"(?:[^"\\]|\\.)*")*?)`

/**
 * Matches a whole `image-gallery` block. Group 1 is the opening tag's raw
 * params, group 2 everything up to the closing tag.
 *
 * Unlike most of our shortcode handling this cannot use `Shortcode.regex`,
 * which matches a single tag at a time. A gallery is inherently a paired
 * shortcode, so the whole block has to be consumed at once — otherwise the
 * opening tag, the items and the closing tag would be converted independently
 * and there would be nothing tying them together in the editor.
 *
 * The lookahead after the name keeps `image-gallery-item` from being taken for
 * an opening tag. Both `{{< /image-gallery >}}` and `{{</ image-gallery >}}`
 * close a gallery, since both appear in the wild.
 */
const GALLERY_BLOCK_REGEX = new RegExp(
  String.raw`\{\{<\s*image-gallery(?=[\s>])${RAW_PARAMS}>\}\}([\s\S]*?)\{\{<\s*\/\s*image-gallery\s*>\}\}`,
  "g",
)

const GALLERY_ITEM_REGEX = new RegExp(
  String.raw`\{\{<\s*image-gallery-item(?=[\s/>])${RAW_PARAMS}>\}\}`,
  "g",
)

/**
 * Showdown rewrites a few characters before any extension sees the Markdown,
 * and only swaps them back in its final HTML: "$" as "¨D", "¨" as "¨T", and a
 * non-breaking space as "&nbsp;". Params captured here end up in an encoded
 * attribute, out of that final pass's reach, so swap them back first, in the
 * same order showdown does.
 *
 * "$" and "¨" come back exactly. A literal "&nbsp;" typed into a param cannot
 * be told apart from one showdown wrote, so it is saved as the non-breaking
 * space character it stands for. Hugo renders an item's text identically
 * either way, and no gallery in production contains the entity; keeping it
 * would need a hook before showdown's normalisation, in the shared Markdown
 * plugin.
 */
const undoShowdownEscapes = (text: string): string =>
  text
    .replace(/¨D/g, () => "$")
    .replace(/¨T/g, "¨")
    .replace(/&nbsp;/g, "\u00a0")

/**
 * URL-encode text for an HTML attribute, including the few characters that
 * encodeURIComponent leaves alone, so that nothing Markdown or a later syntax
 * extension acts on (`*`, `(`, `{{<` and the like) is left in the HTML.
 * LegacyShortcodes, for one, would otherwise convert the `{{< sub 2 >}}`
 * inside a caption.
 */
const encodeAttribute = (text: string): string =>
  encodeURIComponent(text).replace(
    /[!'()*~]/g,
    (char) => `%${char.charCodeAt(0).toString(16).toUpperCase()}`,
  )

const decodeAttribute = (value: string | null | undefined): string => {
  try {
    return decodeURIComponent(value ?? "")
  } catch {
    return ""
  }
}

/** Read the JSON list of raw item params kept on the model element. */
const parseItems = (json: string | null | undefined): string[] => {
  try {
    const items = JSON.parse(json || "[]")
    return Array.isArray(items)
      ? items.filter((item): item is string => typeof item === "string")
      : []
  } catch {
    return []
  }
}

/** A blank run of params is written as one space: `{{< image-gallery >}}`. */
const shortcodeTag = (name: string, rawParams: string): string =>
  `{{< ${name}${rawParams.trim() ? rawParams : " "}>}}`

const serializeGallery = (params: string, items: string[]): string =>
  [
    shortcodeTag("image-gallery", params),
    ...items.map((item) => shortcodeTag("image-gallery-item", item)),
    "{{< /image-gallery >}}",
  ].join("\n")

/**
 * Markdown conversion rules for image galleries.
 *
 * A whole gallery becomes a single `div.image-gallery` carrying, URL-encoded,
 * the opening tag's raw params and a JSON list of each item's raw params.
 * Both are written back exactly as they came in, which matters because two
 * themes read different params: course-v2 uses `baseUrl`, `href` and `text`,
 * course-v3 uses `uuid`, and the editor needs to understand neither. Items stay
 * out of the CKEditor schema: the editor only adds, removes and reorders whole
 * items, so a flat node is enough.
 *
 * Only the closing tag (always `{{< /image-gallery >}}`) and the whitespace
 * between items (one item per line) are normalised.
 */
class ImageGalleryMarkdownSyntax extends MarkdownSyntaxPlugin {
  static get pluginName(): string {
    return "ImageGalleryMarkdownSyntax"
  }

  get showdownExtension() {
    return function imageGalleryExtension(): Showdown.ShowdownExtension[] {
      return [
        {
          type: "lang",
          regex: GALLERY_BLOCK_REGEX,
          replace: (_match: string, params: string, interior: string) => {
            const items = [...interior.matchAll(GALLERY_ITEM_REGEX)].map(
              (match) => undoShowdownEscapes(match[1]),
            )
            return `<div class="${GALLERY_CLASS}" ${DATA_PARAMS}="${encodeAttribute(
              undoShowdownEscapes(params),
            )}" ${DATA_ITEMS}="${encodeAttribute(JSON.stringify(items))}"></div>`
          },
        },
      ]
    }
  }

  get turndownRules(): TurndownRule[] {
    return [
      {
        name: "imageGallery",
        rule: {
          // Filtering on the class rather than the tag name matters: `div` is
          // far too broad, and ResourceEmbed already claims `section`.
          filter: (node: Turndown.Node): boolean =>
            node.nodeName === "DIV" &&
            (node as HTMLElement).classList.contains(GALLERY_CLASS),
          replacement: (_content: string, node: Turndown.Node): string => {
            if (!(node instanceof HTMLElement)) {
              throw new Error("Node should be HTMLElement")
            }
            const items = parseItems(
              decodeAttribute(node.getAttribute(DATA_ITEMS)),
            )
            // An empty gallery is not worth writing to the repo, and a bare
            // pair of shortcodes would render as an empty div on the site.
            if (items.length === 0) {
              return ""
            }
            const params = decodeAttribute(node.getAttribute(DATA_PARAMS))
            return `${serializeGallery(params, items)}\n`
          },
        },
      },
    ]
  }
}

/**
 * Inserts a new gallery at the selection, given its opening tag's raw params
 * and each item's raw params.
 */
class InsertImageGalleryCommand extends Command {
  constructor(editor: Editor) {
    super(editor)
  }

  execute({ params, items }: { params: string; items: string[] }) {
    this.editor.model.change((writer: any) => {
      const gallery = writer.createElement(IMAGE_GALLERY, {
        [PARAMS]: params,
        [ITEMS]: JSON.stringify(items),
      })
      this.editor.model.insertContent(gallery)
    })
  }

  refresh() {
    const model = this.editor.model
    const selection = model.document.selection
    const position = selection.getFirstPosition()
    // A selection with no position has nowhere to insert into, so the command
    // is simply unavailable rather than being asked about an absent position.
    const allowedIn = position
      ? model.schema.findAllowedParent(position, IMAGE_GALLERY)
      : null
    this.isEnabled = allowedIn !== null
  }
}

class ImageGalleryEditing extends CKEPlugin {
  static get pluginName(): string {
    return "ImageGalleryEditing"
  }

  constructor(editor: Editor) {
    super(editor)
  }

  init() {
    this._defineSchema()
    this._defineConverters()

    this.editor.commands.add(
      IMAGE_GALLERY_COMMAND,
      new InsertImageGalleryCommand(this.editor),
    )
  }

  _defineSchema() {
    this.editor.model.schema.register(IMAGE_GALLERY, {
      isObject: true,
      allowWhere: "$block",
      // `items` is stored as a JSON string rather than an array. CKEditor
      // treats attribute values as opaque and compares them by identity in
      // places, so a primitive keeps change detection and undo/redo
      // predictable.
      allowAttributes: [PARAMS, ITEMS],
    })
  }

  _defineConverters() {
    const conversion = this.editor.conversion
    const editor = this.editor

    conversion.for("upcast").elementToElement({
      view: {
        name: "div",
        classes: [GALLERY_CLASS],
      },
      model: (viewElement: any, { writer: modelWriter }: any) =>
        modelWriter.createElement(IMAGE_GALLERY, {
          [PARAMS]: decodeAttribute(viewElement.getAttribute(DATA_PARAMS)),
          [ITEMS]: JSON.stringify(
            parseItems(decodeAttribute(viewElement.getAttribute(DATA_ITEMS))),
          ),
        }),
    })

    conversion.for("dataDowncast").elementToElement({
      model: IMAGE_GALLERY,
      view: (modelElement: any, { writer: viewWriter }: any) =>
        viewWriter.createRawElement(
          "div",
          {
            class: GALLERY_CLASS,
            [DATA_PARAMS]: encodeAttribute(
              modelElement.getAttribute(PARAMS) ?? "",
            ),
            [DATA_ITEMS]: encodeAttribute(
              JSON.stringify(parseItems(modelElement.getAttribute(ITEMS))),
            ),
          },
          function (el: HTMLElement) {
            // Some text inside keeps Turndown from classing the div as blank,
            // which would skip every rule and drop the gallery. The rule above
            // ignores it. LegacyShortcodes does the same.
            el.textContent = GALLERY_CLASS
          },
        ),
    })

    const { renderImageGallery, openImageGalleryPicker } = (editor.config.get(
      CKEDITOR_RESOURCE_UTILS,
    ) ?? {}) as {
      renderImageGallery?: RenderGalleryFunc
      openImageGalleryPicker?: (handle: ImageGalleryHandle) => void
    }

    conversion.for("editingDowncast").elementToElement({
      model: IMAGE_GALLERY,
      view: (modelElement: any, { writer: viewWriter }: any) => {
        const container = viewWriter.createContainerElement("div", {
          class: "image-gallery-widget",
        })

        /**
         * The handle closes over this gallery's model element, so every
         * mutation the React layer makes goes through `model.change()` and
         * therefore participates in undo/redo and marks the form dirty.
         *
         * Note there is deliberately no reconversion configured for the
         * `items` attribute. Reconversion would rebuild this view element on
         * every change, destroying the raw element's DOM node and remounting
         * the React tree mid-drag. Instead React subscribes to model changes
         * and re-renders in place.
         */
        const handle: ImageGalleryHandle = {
          getItems: () => parseItems(modelElement.getAttribute(ITEMS)),
          setItems: (items: string[]) =>
            editor.model.change((writer: any) =>
              writer.setAttribute(ITEMS, JSON.stringify(items), modelElement),
            ),
          onModelChange: (cb: () => void) => {
            const listener = () => cb()
            editor.model.document.on("change:data", listener)
            return () => editor.model.document.off("change:data", listener)
          },
          openPicker: () => openImageGalleryPicker?.(handle),
        }

        /**
         * data-cke-ignore-events makes CKEditor ignore DOM events from inside
         * the widget's interior. Its buttons and drag handles are operated by
         * mouse and keyboard, and without this CKEditor would also act on
         * those events, e.g. selecting the widget on mousedown, or moving its
         * caret beside the widget and cancelling the key's default action on
         * an arrow key. That includes its undo and redo shortcuts, so the
         * wrapper handles those itself.
         */
        const reactWrapper = viewWriter.createRawElement(
          "div",
          {
            class: "image-gallery-react-wrapper",
            "data-cke-ignore-events": "true",
          },
          function (el: HTMLElement) {
            el.addEventListener("keydown", (event) => {
              const command = HISTORY_KEYSTROKES.get(getCode(event))
              if (command && editor.commands.get(command)) {
                editor.execute(command)
                event.preventDefault()
              }
            })
            renderImageGallery?.(el, handle)
          },
        )

        viewWriter.insert(
          viewWriter.createPositionAt(container, 0),
          reactWrapper,
        )

        return toWidget(container, viewWriter, { label: "Image Gallery" })
      },
    })
  }
}

/**
 * Toolbar button which opens the resource picker and inserts whatever the user
 * chooses as a new gallery.
 */
class ImageGalleryToolbar extends CKEPlugin {
  static get pluginName(): string {
    return "ImageGalleryToolbar"
  }

  init(): void {
    const editor = this.editor
    const { openImageGalleryPicker } = (editor.config.get(
      CKEDITOR_RESOURCE_UTILS,
    ) ?? {}) as {
      openImageGalleryPicker?: (handle: ImageGalleryHandle | null) => void
    }

    editor.ui.componentFactory.add(ADD_IMAGE_GALLERY, (locale: any) => {
      const view = new ButtonView(locale)

      view.set({
        label: "Image gallery",
        withText: true,
      })

      view.on("execute", () => {
        // No handle: the picker's selection becomes a brand new gallery.
        openImageGalleryPicker?.(null)
      })

      return view
    })
  }
}

/**
 * CKEditor plugin providing viewable, reorderable image galleries.
 *
 * Galleries are stored in Markdown as a paired Hugo shortcode. Every param on
 * either tag is kept as authored; items Studio adds carry `uuid` for course-v3
 * and `href` and `text` for course-v2 (see galleryItems.ts):
 *
 *   {{< image-gallery baseUrl="/courses/..." >}}
 *   {{< image-gallery-item uuid="..." href="..." text="..." >}}
 *   {{< /image-gallery >}}
 */
export default class ImageGallery extends CKEPlugin {
  static get pluginName(): string {
    return "ImageGallery"
  }

  static get requires(): (typeof CKEPlugin)[] {
    return [
      ImageGalleryEditing,
      ImageGalleryMarkdownSyntax,
      ImageGalleryToolbar,
    ]
  }
}
