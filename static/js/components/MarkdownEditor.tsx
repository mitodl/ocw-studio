import React, { useEffect, useRef } from "react"
import _ from "lodash"

import CKEditor from "../lib/ckeditor"

type Props = {
  initialData: string
  onChange: Function
}

const editorClassName = (readOnly?: boolean): string =>
  `ck-editor ${readOnly ? "read-only" : ""}`.trim()

export default function MarkdownEditor(props: Props): React.ReactElement {
  const { initialData, onChange } = props

  const editor = useRef<typeof CKEditor | null>(null)
  const editorEl = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const attachEditorToRef = async () => {
      if (editorEl.current) {
      const editorInstance = await CKEditor.create(initialData)

      editorInstance.model.document.on(
        "change:data",
        // editor.getData() is kind of expensive so we debounce
        _.debounce(() => {
          if (onChange) {
            onChange(editorInstance.getData())
          }
        }, 250)
      )

      editorEl.current.appendChild(editorInstance.ui.view.toolbar.element)
      editorEl.current.appendChild(editorInstance.ui.view.editable.element)
      editor.current = editorInstance
      }
    }
    if (editorEl.current) {
      attachEditorToRef()
    }

    return () => {
      (async function () {
        if (editor.current !== null) {
          await editor.current.destroy()
        }
      })()
    }
  }, [ editorEl.current ])

  return (
    <div className="markdown-editor" ref={editorEl} />
    )
}
