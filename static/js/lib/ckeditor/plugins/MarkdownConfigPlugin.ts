import { Editor, Plugin } from "@ckeditor/ckeditor5-core"

import { MarkdownConfig } from "../../../types/ckeditor_markdown"
import { MARKDOWN_CONFIG_KEY } from "./constants"
import { getOcwConfig } from "./util"

/**
 * Abstract class providing functionality to get and set the
 * Markdown-specific functionality. Plugins for adding Markdown
 * syntax rules need to inherit from this plugin.
 */
export default abstract class MarkdownConfigPlugin extends Plugin {
  /**
   * `allowedHtml` is defaulted here as well. `getMarkdownConfig` has always
   * claimed to return a complete `MarkdownConfig`, but an editor booted
   * without a `markdown-config` entry used to get `allowedHtml: undefined`,
   * which `Markdown` then handed to `turndownService.keep()`.
   */
  static defaults: MarkdownConfig = {
    showdownExtensions: [],
    turndownRules: [],
    allowedHtml: [],
  }

  constructor(editor: Editor) {
    super(editor)
  }

  /**
   * Returns the Markdown configuration set on this.editor
   */
  getMarkdownConfig(): MarkdownConfig {
    const provided = getOcwConfig(this.editor, MARKDOWN_CONFIG_KEY)

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
