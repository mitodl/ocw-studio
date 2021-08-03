import React, { useCallback, useRef } from "react"
import { CKEditor } from "@ckeditor/ckeditor5-react"
import { editor } from "@ckeditor/ckeditor5-core"
import ClassicEditor from "@ckeditor/ckeditor5-editor-classic/src/classiceditor"

import {
  FullEditorConfig,
  MinimalEditorConfig
} from "../../lib/ckeditor/CKEditor"
import ResourceEmbedField from "./ResourceEmbedField"
import { RESOURCE_EMBED_COMMAND } from "../../lib/ckeditor/plugins/ResourceEmbed"

export interface Props {
  value?: string
  name?: string
  onChange?: (event: { target: { value: string; name: string } }) => void
  children?: React.ReactNode
  minimal?: boolean
  attach?: string
}

/**
 * A component for editing Markdown using CKEditor.
 *
 * pass minimal: true to get a minimal version.
 */
export default function MarkdownEditor(props: Props): JSX.Element {
  const { attach, value, name, onChange, minimal } = props

  const editor = useRef<editor.Editor>()
  const setEditorRef = useCallback(editorInstance => {
    editor.current = editorInstance
  }, [])

  const addResourceEmbed = useCallback(
    (id: string) => {
      if (editor.current) {
        editor.current.execute(RESOURCE_EMBED_COMMAND, id)
        // @ts-ignore
        editor.current.editing.view.focus()
      }
    },
    [editor]
  )

  return (
    <>
      <CKEditor
        editor={ClassicEditor}
        config={minimal ? MinimalEditorConfig : FullEditorConfig}
        data={value ?? ""}
        onReady={setEditorRef}
        onChange={(_event: any, editor: any) => {
          const data = editor.getData()
          if (onChange) {
            onChange({ target: { name: name ?? "", value: data } })
          }
        }}
      />
      {attach && attach.length !== 0 ? (
        <ResourceEmbedField insertEmbed={addResourceEmbed} attach={attach} />
      ) : null}
    </>
  )
}
