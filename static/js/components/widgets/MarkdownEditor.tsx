import React from "react"
import { CKEditor } from "@ckeditor/ckeditor5-react"

import ClassicEditor from "@ckeditor/ckeditor5-editor-classic/src/classiceditor"

import {
  FullEditorConfig,
  MinimalEditorConfig
} from "../../lib/ckeditor/CKEditor"

export interface Props {
  value?: string
  name?: string
  onChange?: (event: { target: { value: string; name: string } }) => void
  children?: React.ReactNode
  minimal?: boolean
}

/**
 * A component for editing Markdown using CKEditor.
 */
export function MarkdownEditor(props: Props): JSX.Element {
  const { value, name, onChange, minimal } = props

  return (
    <CKEditor
      editor={ClassicEditor}
      config={minimal ? MinimalEditorConfig : FullEditorConfig}
      data={value ?? ""}
      onChange={(event: any, editor: any) => {
        const data = editor.getData()
        if (onChange) {
          onChange({ target: { name: name ?? "", value: data } })
        }
      }}
    />
  )
}

export function MinimalMarkdownEditor(props: Props): JSX.Element {
  return <MarkdownEditor {...props} minimal={true} />
}
