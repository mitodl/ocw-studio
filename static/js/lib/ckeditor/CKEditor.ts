import EssentialsPlugin from "@ckeditor/ckeditor5-essentials/src/essentials"
import AutoformatPlugin from "@ckeditor/ckeditor5-autoformat/src/autoformat"
import BoldPlugin from "@ckeditor/ckeditor5-basic-styles/src/bold"
import ItalicPlugin from "@ckeditor/ckeditor5-basic-styles/src/italic"
import UnderlinePlugin from "@ckeditor/ckeditor5-basic-styles/src/underline"
import BlockQuotePlugin from "@ckeditor/ckeditor5-block-quote/src/blockquote"
import HeadingPlugin from "@ckeditor/ckeditor5-heading/src/heading"
import ImagePlugin from "@ckeditor/ckeditor5-image/src/image"
import ImageCaptionPlugin from "@ckeditor/ckeditor5-image/src/imagecaption"
import ImageStylePlugin from "@ckeditor/ckeditor5-image/src/imagestyle"
import ImageToolbarPlugin from "@ckeditor/ckeditor5-image/src/imagetoolbar"
import LinkPlugin from "@ckeditor/ckeditor5-link/src/link"
import ListPlugin from "@ckeditor/ckeditor5-list/src/list"
import ParagraphPlugin from "@ckeditor/ckeditor5-paragraph/src/paragraph"
import TablePlugin from "@ckeditor/ckeditor5-table/src/table"
import TableToolbarPlugin from "@ckeditor/ckeditor5-table/src/tabletoolbar"
import CodeBlockPlugin from "@ckeditor/ckeditor5-code-block/src/codeblock"
import CodePlugin from "@ckeditor/ckeditor5-basic-styles/src/code"

import { editor } from "@ckeditor/ckeditor5-core"

import Markdown from "./plugins/Markdown"
import ResourceEmbed from "./plugins/ResourceEmbed"
import ResourcePicker from "./plugins/ResourcePicker"
import { ADD_RESOURCE_EMBED, ADD_RESOURCE_LINK } from "./plugins/constants"
import ResourceLink from "@mitodl/ckeditor5-resource-link/src/link"
import { RESOURCE_LINK_COMMAND } from "@mitodl/ckeditor5-resource-link/src/constants"
import ResourceLinkMarkdownSyntax, {
  encodeShortcodeArgs
} from "./plugins/ResourceLinkMarkdownSyntax"
import DisallowNestedTables from "./plugins/DisallowNestedTables"
import TableMarkdownSyntax from "./plugins/TableMarkdownSyntax"
import MarkdownListSyntax from "./plugins/MarkdownListSyntax"
import LegacyShortcodes from "./plugins/LegacyShortcodes"

/**
 * Programming languages we support in CKEditor code blocks
 *
 * This list is based on CKEditor's default list, here:
 *
 * https://github.com/ckeditor/ckeditor5/blob/master/packages/ckeditor5-code-block/src/codeblockediting.js#L60
 *
 * extended with a few more options.
 */
const SUPPORTED_PROGRAMMING_LANGUAGES = [
  { language: "plaintext", label: "Plain text" },
  { language: "matlab", label: "Matlab" },
  { language: "julia", label: "Julia" },
  { language: "c", label: "C" },
  { language: "cs", label: "C#" },
  { language: "cpp", label: "C++" },
  { language: "css", label: "CSS" },
  { language: "diff", label: "Diff" },
  { language: "html", label: "HTML" },
  { language: "java", label: "Java" },
  { language: "javascript", label: "JavaScript" },
  { language: "php", label: "PHP" },
  { language: "python", label: "Python" },
  { language: "ruby", label: "Ruby" },
  { language: "typescript", label: "TypeScript" },
  { language: "xml", label: "XML" }
].sort((first, second) => {
  const labelOne = first.label.toUpperCase()
  const labelTwo = second.label.toUpperCase()

  if (labelOne < labelTwo) {
    return -1
  }
  if (labelOne > labelTwo) {
    return 1
  }
  return 0
})

export const FullEditorConfig = {
  plugins: [
    EssentialsPlugin,
    AutoformatPlugin,
    BoldPlugin,
    ItalicPlugin,
    // note that this is just for inline (not block-level) code
    CodePlugin,
    UnderlinePlugin,
    BlockQuotePlugin,
    HeadingPlugin,
    ImagePlugin,
    ImageCaptionPlugin,
    ImageStylePlugin,
    ImageToolbarPlugin,
    LinkPlugin,
    ListPlugin,
    ParagraphPlugin,
    TablePlugin,
    TableToolbarPlugin,
    CodeBlockPlugin,
    ResourceEmbed,
    ResourcePicker,
    ResourceLink,
    ResourceLinkMarkdownSyntax,
    TableMarkdownSyntax,
    MarkdownListSyntax,
    LegacyShortcodes,
    Markdown,
    DisallowNestedTables
  ],
  toolbar: {
    items: [
      "heading",
      "|",
      "bold",
      "italic",
      "underline",
      "link",
      "bulletedList",
      "numberedList",
      "blockQuote",
      "code",
      "codeBlock",
      "insertTable",
      "undo",
      "redo",
      ADD_RESOURCE_LINK,
      ADD_RESOURCE_EMBED
    ]
  },
  image: {
    toolbar: ["imageStyle:full", "imageStyle:side", "|", "imageTextAlternative"]
  },
  codeBlock: {
    languages: SUPPORTED_PROGRAMMING_LANGUAGES
  },
  table: {
    contentToolbar:  ["tableColumn", "tableRow", "mergeTableCells"],
    defaultHeadings: { rows: 1 }
  },
  language: "en"
}

export const MinimalEditorConfig = {
  plugins: [
    EssentialsPlugin,
    AutoformatPlugin,
    BoldPlugin,
    ItalicPlugin,
    CodePlugin,
    UnderlinePlugin,
    BlockQuotePlugin,
    LinkPlugin,
    ListPlugin,
    ParagraphPlugin,
    ResourceEmbed,
    ResourcePicker,
    ResourceLink,
    ResourceLinkMarkdownSyntax,
    MarkdownListSyntax,
    Markdown,
    LegacyShortcodes
  ],
  toolbar: {
    items: [
      "bold",
      "italic",
      "underline",
      "code",
      "link",
      "bulletedList",
      "numberedList",
      "blockQuote",
      "undo",
      "redo",
      ADD_RESOURCE_LINK,
      ADD_RESOURCE_EMBED
    ]
  },
  language: "en"
}

export const insertResourceLink = (
  editor: editor.Editor,
  uuid: string,
  title: string
) => {
  const encoded = encodeShortcodeArgs(uuid)
  editor.execute(RESOURCE_LINK_COMMAND, encoded, title)
}
