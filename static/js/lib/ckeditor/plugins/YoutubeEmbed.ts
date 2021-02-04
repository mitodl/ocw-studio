import Plugin from "@ckeditor/ckeditor5-core/src/plugin"
import Command from "@ckeditor/ckeditor5-core/src/command"
import ButtonView from "@ckeditor/ckeditor5-ui/src/button/buttonview"
import { createDropdown } from "@ckeditor/ckeditor5-ui/src/dropdown/utils"
import {
  YOUTUBE_EMBED_CLASS,
  youtubeEmbedUrl,
  YOUTUBE_EMBED_PARAMS
} from "../../markdown"
import {
  toWidget,
  toWidgetEditable
} from "@ckeditor/ckeditor5-widget/src/utils"
import Widget from "@ckeditor/ckeditor5-widget/src/widget"
import MediaFormView from "@ckeditor/ckeditor5-media-embed/src/ui/mediaformview"
import InputTextView from "@ckeditor/ckeditor5-ui/src/inputtext/inputtextview"

class YoutubeEmbedUI extends Plugin {
  init() {
    const editor = this.editor
    const t = editor.t

    editor.commands.add(
      "insertYoutubeEmbed",
      new InsertYoutubeEmbedCommand(this.editor)
    )

    editor.ui.componentFactory.add("youtubeEmbed", (locale: any) => {
      const command = editor.commands.get("insertYoutubeEmbed")

      const dropdown = createDropdown(locale)
      const input = new InputTextView()
      dropdown.panelView.children.add(input)

      dropdown.buttonView.set({
        label:    "Insert YouTube",
        withText: true
      })

      const saveButton = new ButtonView(this.locale)
      saveButton.set({
        label:    "Save",
        withText: true
      })

      saveButton.extendTemplate({
        attributes: {
          class: "ck-button-save"
        }
      })
      saveButton.type = "submit"
      saveButton.delegate("execute").to(dropdown, "submit")
      dropdown.panelView.children.add(saveButton)

      dropdown.on("submit", () => {
        const videoId = input.element.value
        if (videoId) {
          editor.execute("insertYoutubeEmbed", videoId)
          closeUI()
        }
      })

      dropdown.on("cancel", () => closeUI())

      function closeUI() {
        editor.editing.view.focus()
        dropdown.isOpen = false
      }

      return dropdown
    })
  }
}

class YoutubeEmbedEditing extends Plugin {
  init() {
    this._defineSchema()
    this._defineConverters()
  }

  _defineSchema() {
    const schema = this.editor.model.schema

    schema.register("youtubeEmbed", {
      isObject:       true,
      allowWhere:     "$block",
      allowContentOf: "$block"
    })
  }

  _defineConverters() {
    const conversion = this.editor.conversion

    /**
     * `upcast` converts the HTML string to a view element (i.e. ckeditor
     * internal state, *not* to a DOM element)
     *
     * providing 'iframe' and YOUTUBE_EMBED_CLASS allows CKEditor to recognize
     * the iframe in our converted HTML and convert it to a `youtubeEmbed` object
     */
    conversion.for("upcast").elementToElement({
      model: "youtubeEmbed",
      view:  {
        name:    "section",
        classes: YOUTUBE_EMBED_CLASS
      }
    })

    /**
     * dataDowncast converts a view element to an HTML element for data
     * output (this output will then be the input into our html2md function)
     */
    conversion.for("dataDowncast").elementToElement({
      model: "youtubeEmbed",
      view:  {
        name:    "section",
        classes: YOUTUBE_EMBED_CLASS
      }
    })

    /**
     * editingDowncast converts a view element to HTML which is actually shown
     * in the editor for WYSIWYG purposes
     * (for the youtube embed this is an iframe)
     */
    conversion.for("editingDowncast").elementToElement({
      model: "youtubeEmbed",
      view:  (modelElement: any, { writer: viewWriter }: any) => {
        const videoId = modelElement._children._nodes[0]._data
        const iframe = viewWriter.createContainerElement("iframe", {
          class: YOUTUBE_EMBED_CLASS,
          src:   youtubeEmbedUrl(videoId),
          ...YOUTUBE_EMBED_PARAMS
        })
        return toWidget(iframe, viewWriter, { label: "Youtube Embed" })
      }
    })
  }
}

export default class YoutubeEmbed extends Plugin {
  static get requires() {
    return [YoutubeEmbedEditing, YoutubeEmbedUI]
  }
}

export class InsertYoutubeEmbedCommand extends Command {
  constructor(editor: any) {
    super(editor)
  }

  execute(videoId: string) {
    this.editor.model.change((writer: any) => {
      this.editor.model.insertContent(
        createYoutubeEmbed(writer, videoId),
        this.editor.model.document.selection
      )
    })
  }

  refresh() {
    const model = this.editor.model
    const selection = model.document.selection
    const allowedIn = model.schema.findAllowedParent(
      selection.getFirstPosition(),
      "youtubeEmbed"
    )

    this.isEnabled = allowedIn !== null
  }
}

function createYoutubeEmbed(writer: any, videoId: string) {
  const embed = writer.createElement("youtubeEmbed")
  const text = writer.createText(videoId)
  writer.append(text, embed)
  return embed
}
