import Plugin from "@ckeditor/ckeditor5-core/src/plugin"
import { Editor } from "@ckeditor/ckeditor5-core"

import { MarkdownConfig } from "../../../types/ckeditor_markdown"
import { MARKDOWN_CONFIG_KEY } from "./constants"

/**
 * Abstract class providing functionality to get and set the
 * Markdown-specific functionality. Plugins for adding Markdown
 * syntax rules need to inherit from this plugin.
 */
export default abstract class MarkdownConfigPlugin extends Plugin {
  static defaults = {
    showdownExtensions: [],
    turndownRules:      []
  }

  constructor(editor: Editor) {
    super(editor)
  }

  /**
   * Returns the Markdown configuration set on this.editor
   */
  getMarkdownConfig(): MarkdownConfig {
    const provided = this.editor.config.get(MARKDOWN_CONFIG_KEY)

    return { ...MarkdownConfigPlugin.defaults, ...provided }
  }

  /**
   * Set the Markdown config on this.editor, to be used later
   * when instanting the DataProcessor.
   */
  setMarkdownConfig(newConfig: MarkdownConfig): void {
    this.editor.config.set(MARKDOWN_CONFIG_KEY, newConfig)
  }
}
