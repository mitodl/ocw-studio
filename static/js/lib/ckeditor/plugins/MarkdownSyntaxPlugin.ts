import { Editor } from "@ckeditor/ckeditor5-core"
import Showdown from "showdown"

import MarkdownConfigPlugin from "./MarkdownConfigPlugin"
import { TurndownRule } from "../../../types/ckeditor_markdown"

/**
 * Plugin for extending Markdown syntax. Each plugin that needs to
 * extend Markdown syntax to support a new node type should declare
 * a syntax plugin inheriting from this class.
 */
export default abstract class MarkdownSyntaxPlugin extends MarkdownConfigPlugin {
  constructor(editor: Editor) {
    super(editor)
    this.loadMarkdownSyntax()
  }

  /**
   * load Markdown syntax rules from class properties and
   * assign them to the config on this.editor
   *
   * this is implemented as a separate method because Typescript
   * does not allow accessing abstract properties in the constructor
   */
  loadMarkdownSyntax(): void {
    const currentConfig = this.getMarkdownConfig()
    const newConfig = {
      ...currentConfig,
      showdownExtensions: [
        ...currentConfig.showdownExtensions,
        this.showdownExtension,
      ],
      turndownRules: [...currentConfig.turndownRules, ...this.turndownRules],
    }
    this.setMarkdownConfig(newConfig)
  }

  abstract get showdownExtension(): () => Showdown.ShowdownExtension[]

  abstract get turndownRules(): TurndownRule[]
}
