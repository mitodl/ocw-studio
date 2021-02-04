import React from "react"
import { CKEditor } from "@ckeditor/ckeditor5-react"

import OurEditor from "../lib/ckeditor/CKEditor"

export interface Props {
  initialData?: string
  onChange?: (s: string) => void
  children?: React.ReactNode
}

/**
 * A component for editing Markdown using CKEditor.
 */
export default function MarkdownEditor(props: Props): JSX.Element {
  const { initialData, onChange } = props

  return (
    <CKEditor
      editor={OurEditor}
      data={initialData ?? ""}
      onChange={(event: any, editor: any) => {
        const data = editor.getData()
        if (onChange) {
          onChange(data)
        }
      }}
    />
  )
}
