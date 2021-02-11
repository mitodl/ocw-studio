import Plugin from "@ckeditor/ckeditor5-core/src/plugin"
import Command from "@ckeditor/ckeditor5-core/src/command"
import ButtonView from "@ckeditor/ckeditor5-ui/src/button/buttonview"
import { YOUTUBE_EMBED_CLASS, youtubeEmbedUrl, YOUTUBE_EMBED_PARAMS } from "../../markdown"
import { toWidget, toWidgetEditable } from '@ckeditor/ckeditor5-widget/src/utils';
import Widget from '@ckeditor/ckeditor5-widget/src/widget';

class YoutubeEmbedUI extends Plugin {
  init() {
    const editor = this.editor
    const t = editor.t

    // The "simpleBox" button must be registered among the UI components of the editor
    // to be displayed in the toolbar.
    editor.ui.componentFactory.add("youtubeEmbed", (locale: any) => {
      // The state of the button will be bound to the widget command.
      const command = editor.commands.get("insertYoutubeEmbed")

      // The button will be an instance of ButtonView.
      const buttonView = new ButtonView(locale)

      buttonView.set({
        // The t() function helps localize the editor. All strings enclosed in t() can be
        // translated and change when the language of the editor changes.
        label:    t("Embed Youtube Video"),
        withText: true,
        tooltip:  true
      })

      // Bind the state of the button to the command.
      buttonView.bind("isOn", "isEnabled").to(command, "value", "isEnabled")

      // Execute the command when the button is clicked (executed).
      this.listenTo(buttonView, "execute", () =>
        editor.execute("insertYoutubeEmbed")
      )

      return buttonView
    })
  }
}

class YoutubeEmbedEditing extends Plugin {
  init() {
    console.log("SimpleBoxEditing#init() got called")

    this._defineSchema()
    this._defineConverters()
    this.editor.commands.add(
      "insertYoutubeEmbed",
      new InsertYoutubeEmbedCommand(this.editor)
    )
  }

  _defineSchema() {
    const schema = this.editor.model.schema

    schema.register("youtubeEmbed", {
      isObject:   true,
      allowWhere: "$block",
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
        // this looks bad but I promise it's fine
        const videoId = modelElement._children._nodes[0]._data
        const iframe = viewWriter.createContainerElement("iframe", {
          class: YOUTUBE_EMBED_CLASS,
          src: youtubeEmbedUrl(videoId),
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

  execute() {
    this.editor.model.change((writer: any) => {
      // Insert <simpleBox>*</simpleBox> at the current selection position
      // in a way that will result in creating a valid model structure.
      this.editor.model.insertContent(createYoutubeEmbed(writer))
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

function createYoutubeEmbed(writer: any) {
  const embed = writer.createElement("youtubeEmbed")
  const videoId = writer.createElement("youtubeVideoId")

  writer.append(videoId, embed)

  return embed
}
