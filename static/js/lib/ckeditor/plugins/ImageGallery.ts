import CKEPlugin from "@ckeditor/ckeditor5-core/src/plugin"
import Command from "@ckeditor/ckeditor5-core/src/command"
import Showdown from "showdown"
import Turndown from "turndown"
import { Editor } from "@ckeditor/ckeditor5-core"
import { toWidget } from "@ckeditor/ckeditor5-widget/src/utils"
import ButtonView from "@ckeditor/ckeditor5-ui/src/button/buttonview"

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
const DATA_UUIDS = "data-uuids"
const UUIDS = "uuids"

/**
 * Matches a whole `image-gallery` block, capturing everything between the
 * opening and closing shortcodes.
 *
 * Unlike most of our shortcode handling this cannot use `Shortcode.regex`,
 * which matches a single tag at a time. A gallery is inherently a paired
 * shortcode, so the whole block has to be consumed at once — otherwise the
 * opening tag, the items and the closing tag would be converted independently
 * and there would be nothing tying them together in the editor.
 *
 * Both `{{< /image-gallery >}}` and `{{</ image-gallery >}}` are accepted for
 * the closing tag, since both appear in the wild.
 */
const GALLERY_BLOCK_REGEX =
  /\{\{<\s*image-gallery\s*>\}\}([\s\S]*?)\{\{<\s*\/\s*image-gallery\s*>\}\}/g

const GALLERY_ITEM_REGEX =
  /\{\{<\s*image-gallery-item\s+uuid="(?<uuid>[^"]*)"\s*\/?\s*>\}\}/g

const parseUuids = (blockInterior: string): string[] =>
  [...blockInterior.matchAll(GALLERY_ITEM_REGEX)]
    .map((match) => match.groups?.uuid ?? "")
    .filter(Boolean)

const serializeUuids = (uuids: string[]): string =>
  [
    "{{< image-gallery >}}",
    ...uuids.map((uuid) => `{{< image-gallery-item uuid="${uuid}" >}}`),
    "{{< /image-gallery >}}",
  ].join("\n")

/**
 * Markdown conversion rules for image galleries.
 *
 * A whole gallery becomes a single `div.image-gallery` carrying its ordered
 * uuids in one attribute. Keeping the items out of the HTML (and out of the
 * CKEditor schema) is deliberate: an item has no authored content of its own
 * any more — description, caption and credit all live on the image resource —
 * so there is nothing for the user to edit per item, and a flat node avoids a
 * nested schema entirely.
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
          replace: (_match: string, interior: string) =>
            `<div class="${GALLERY_CLASS}" ${DATA_UUIDS}="${parseUuids(
              interior,
            ).join(",")}"></div>`,
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
            const uuids = (node.getAttribute(DATA_UUIDS) ?? "")
              .split(",")
              .filter(Boolean)
            // An empty gallery is not worth writing to the repo, and a bare
            // pair of shortcodes would render as an empty div on the site.
            if (uuids.length === 0) {
              return ""
            }
            return `${serializeUuids(uuids)}\n`
          },
        },
      },
    ]
  }
}

/**
 * Inserts a new gallery, or replaces the uuids of the selected one.
 */
class InsertImageGalleryCommand extends Command {
  constructor(editor: Editor) {
    super(editor)
  }

  execute(uuids: string[]) {
    this.editor.model.change((writer: any) => {
      const gallery = writer.createElement(IMAGE_GALLERY, {
        [UUIDS]: uuids.join(","),
      })
      this.editor.model.insertContent(gallery)
    })
  }

  refresh() {
    const model = this.editor.model
    const selection = model.document.selection
    const allowedIn = model.schema.findAllowedParent(
      selection.getFirstPosition(),
      IMAGE_GALLERY,
    )
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
      // Stored as a comma-joined string rather than an array. CKEditor treats
      // attribute values as opaque and compares them by identity in places, so
      // a primitive keeps change detection and undo/redo predictable.
      allowAttributes: [UUIDS],
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
          [UUIDS]: viewElement.getAttribute(DATA_UUIDS) ?? "",
        }),
    })

    conversion.for("dataDowncast").elementToElement({
      model: IMAGE_GALLERY,
      view: (modelElement: any, { writer: viewWriter }: any) =>
        viewWriter.createEmptyElement("div", {
          class: GALLERY_CLASS,
          [DATA_UUIDS]: modelElement.getAttribute(UUIDS) ?? "",
        }),
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
         * `uuids` attribute. Reconversion would rebuild this view element on
         * every change, destroying the raw element's DOM node and remounting
         * the React tree mid-drag. Instead React subscribes to model changes
         * and re-renders in place.
         */
        const handle: ImageGalleryHandle = {
          getUuids: () =>
            (modelElement.getAttribute(UUIDS) ?? "").split(",").filter(Boolean),
          setUuids: (uuids: string[]) =>
            editor.model.change((writer: any) =>
              writer.setAttribute(UUIDS, uuids.join(","), modelElement),
            ),
          onModelChange: (cb: () => void) => {
            const listener = () => cb()
            editor.model.document.on("change:data", listener)
            return () => editor.model.document.off("change:data", listener)
          },
          openPicker: () => openImageGalleryPicker?.(handle),
        }

        const reactWrapper = viewWriter.createRawElement(
          "div",
          { class: "image-gallery-react-wrapper" },
          function (el: HTMLElement) {
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
 * Galleries are stored in Markdown as a paired Hugo shortcode whose items
 * reference image resources by uuid:
 *
 *   {{< image-gallery >}}
 *   {{< image-gallery-item uuid="..." >}}
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
