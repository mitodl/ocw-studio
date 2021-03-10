import React from "react"
import { CKEditor } from "@ckeditor/ckeditor5-react"

import OurEditor from "../lib/ckeditor/CKEditor"

export interface Props {
  value?: string
  name?: string
  onChange?: (event: { target: { value: string; name: string } }) => void
  children?: React.ReactNode
}

/**
 * A component for editing Markdown using CKEditor.
 */
export default function MarkdownEditor(props: Props): JSX.Element {
  const { value, name, onChange } = props

  return (
    <CKEditor
      editor={OurEditor}
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
