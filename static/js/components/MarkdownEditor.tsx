import React, { useEffect, useRef, useCallback } from "react"
import _ from "lodash"

import CKEditor from "../lib/ckeditor/CKEditor"

export interface Props {
  initialData?: string
  onChange?: (s: string) => void
}

/**
 * A component for editing Markdown.
 */
export default function MarkdownEditor(props: Props): JSX.Element {
  const { initialData, onChange } = props

  const editor = useRef<typeof CKEditor | null>(null)
  const editorEl = useRef<HTMLDivElement | null>(null)

  const editorSetupRef = useCallback(async (node: HTMLDivElement) => {
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

    node.appendChild(editorInstance.ui.view.toolbar.element)
    node.appendChild(editorInstance.ui.view.editable.element)
    editor.current = editorInstance
    editorEl.current = node
  }, [])

  useEffect(() => {
    return () => {
      (async function() {
        if (editor.current !== null) {
          await editor.current.destroy()
        }
      })()
    }
  }, [])

  return <div className="markdown-editor ck-editor" ref={editorSetupRef} />
}
