import Plugin from "@ckeditor/ckeditor5-core/src/plugin"
import ButtonView from "@ckeditor/ckeditor5-ui/src/button/buttonview"

import { ADD_RESOURCE, CKEDITOR_RESOURCE_UTILS } from "./constants"

/**
 * Plugin for opening the ResourcePicker
 *
 * This basically just plucks the `openResourcePicker` callback
 * out of our `resourceEmbed` object on `editor.config` and then
 * adds a button to the toolbar which will call that cb on click.
 */
export default class ResourcePicker extends Plugin {
  init(): void {
    const editor = this.editor

    // @ts-ignore
    const { openResourcePicker } =
      this.editor.config.get(CKEDITOR_RESOURCE_UTILS) ?? {}

    editor.ui.componentFactory.add(ADD_RESOURCE, (locale: any) => {
      const view = new ButtonView(locale)

      view.set({
        label:    "Add resource",
        withText: true
      })
      // TODO: icon? how to right-justify?

      view.on("execute", () => {
        openResourcePicker()
      })

      return view
    })
  }
}
