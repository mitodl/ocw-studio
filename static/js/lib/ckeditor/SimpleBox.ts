import Plugin from "@ckeditor/ckeditor5-core/src/plugin"
import Command from "@ckeditor/ckeditor5-core/src/command"
import ButtonView from "@ckeditor/ckeditor5-ui/src/button/buttonview"

class SimpleBoxUI extends Plugin {
  init() {
    console.log("SimpleBoxUI#init() got called")

    const editor = this.editor
    const t = editor.t

    // The "simpleBox" button must be registered among the UI components of the editor
    // to be displayed in the toolbar.
    editor.ui.componentFactory.add("simpleBox", (locale: any) => {
      // The state of the button will be bound to the widget command.
      const command = editor.commands.get("insertSimpleBox")

      // The button will be an instance of ButtonView.
      const buttonView = new ButtonView(locale)

      buttonView.set({
        // The t() function helps localize the editor. All strings enclosed in t() can be
        // translated and change when the language of the editor changes.
        label:    t("Simple Box"),
        withText: true,
        tooltip:  true
      })

      // Bind the state of the button to the command.
      buttonView.bind("isOn", "isEnabled").to(command, "value", "isEnabled")

      // Execute the command when the button is clicked (executed).
      this.listenTo(buttonView, "execute", () =>
        editor.execute("insertSimpleBox")
      )

      return buttonView
    })
  }
}

class SimpleBoxEditing extends Plugin {
  init() {
    console.log("SimpleBoxEditing#init() got called")

    this._defineSchema()
    this._defineConverters()
    this.editor.commands.add(
      "insertSimpleBox",
      new InsertSimpleBoxCommand(this.editor)
    )
  }

  _defineSchema() {
    const schema = this.editor.model.schema

    schema.register("simpleBox", {
      isObject:   true,
      allowWhere: "$block"
    })

    schema.register("simpleBoxTitle", {
      isLimit:        true,
      allowIn:        "simpleBox",
      allowContentOf: "$block"
    })

    schema.register("simpleBoxDescription", {
      isLimit:        true,
      allowIn:        "simpleBox",
      allowContentOf: "$root"
    })
  }

  _defineConverters() {
    // ADDED
    const conversion = this.editor.conversion

    conversion.elementToElement({
      model: "simpleBox",
      view:  {
        name:    "section",
        classes: "simple-box"
      }
    })

    conversion.elementToElement({
      model: "simpleBoxTitle",
      view:  {
        name:    "h1",
        classes: "simple-box-title"
      }
    })

    conversion.elementToElement({
      model: "simpleBoxDescription",
      view:  {
        name:    "div",
        classes: "simple-box-description"
      }
    })
  }
}

export class SimpleBox extends Plugin {
  static get requires() {
    return [SimpleBoxEditing, SimpleBoxUI]
  }
}

export class InsertSimpleBoxCommand extends Command {
  constructor(editor: any) {
    super(editor)
  }

  execute() {
    this.editor.model.change((writer: any) => {
      // Insert <simpleBox>*</simpleBox> at the current selection position
      // in a way that will result in creating a valid model structure.
      this.editor.model.insertContent(createSimpleBox(writer))
    })
  }

  refresh() {
    const model = this.editor.model
    const selection = model.document.selection
    const allowedIn = model.schema.findAllowedParent(
      selection.getFirstPosition(),
      "simpleBox"
    )

    this.isEnabled = allowedIn !== null
  }
}

function createSimpleBox(writer: any) {
  const simpleBox = writer.createElement("simpleBox")
  const simpleBoxTitle = writer.createElement("simpleBoxTitle")
  const simpleBoxDescription = writer.createElement("simpleBoxDescription")

  writer.append(simpleBoxTitle, simpleBox)
  writer.append(simpleBoxDescription, simpleBox)

  // There must be at least one paragraph for the description to be editable.
  // See https://github.com/ckeditor/ckeditor5/issues/1464.
  writer.appendElement("paragraph", simpleBoxDescription)

  return simpleBox
}
