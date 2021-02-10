import Plugin from "@ckeditor/ckeditor5-core/src/plugin"
import Command from "@ckeditor/ckeditor5-core/src/command"
import ButtonView from "@ckeditor/ckeditor5-ui/src/button/buttonview"
import { YOUTUBE_EMBED_CLASS } from '../../markdown'

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
      allowWhere: "$block"
    })

    schema.register("youtubeVideoId", {
      isLimit:        true,
      allowIn:        "simpleBox",
      allowContentOf: "$text"
    })
  }

  _defineConverters() {
    // ADDED
    const conversion = this.editor.conversion

    conversion.elementToElement({
      model: "youtubeEmbed",
      view:  {
        name:    "section",
        classes: "simple-box"
      }
    })

    conversion.elementToElement({
      model: "youtubeEmbed",
      view:  {
        name:    "iframe",
        classes: YOUTUBE_EMBED_CLASS
      }
    })
  }
}

export class YoutubeEmbed extends Plugin {
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

function createSimpleBox(writer: any) {
  const embed = writer.createElement("youtubeEmbed")
  const videoId = writer.createElement("youtubeVideoId")

  writer.append(videoId, embed)

  return embed
}
