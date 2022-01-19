import Plugin from "@ckeditor/ckeditor5-core/src/plugin"
import ButtonView from "@ckeditor/ckeditor5-ui/src/button/buttonview"
import { RESOURCE_LINK } from "@mitodl/ckeditor5-resource-link/src/constants"

import {
  ADD_RESOURCE_EMBED,
  ADD_RESOURCE_LINK,
  CKEDITOR_RESOURCE_UTILS,
  RESOURCE_EMBED
} from "./constants"

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

    editor.ui.componentFactory.add(ADD_RESOURCE_LINK, (locale: any) => {
      const view = new ButtonView(locale)

      view.set({
        label:    "Add link",
        withText: true
      })

      view.on("execute", () => {
        openResourcePicker(RESOURCE_LINK)
      })

      return view
    })

    editor.ui.componentFactory.add(ADD_RESOURCE_EMBED, (locale: any) => {
      const view = new ButtonView(locale)

      view.set({
        label:    "Embed resource",
        withText: true
      })

      view.on("execute", () => {
        openResourcePicker(RESOURCE_EMBED)
      })

      return view
    })
  }
}
