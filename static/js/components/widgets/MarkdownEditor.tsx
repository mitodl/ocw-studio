import React, { useCallback, useMemo, useRef, useState } from "react"
import { CKEditor } from "@ckeditor/ckeditor5-react"
import { editor } from "@ckeditor/ckeditor5-core"
import ClassicEditor from "@ckeditor/ckeditor5-editor-classic/src/classiceditor"

import {
  FullEditorConfig,
  MinimalEditorConfig
} from "../../lib/ckeditor/CKEditor"
import EmbeddedResource from "./EmbeddedResource"
import {
  ADD_RESOURCE_LINK,
  CKEResourceNodeType,
  CKEDITOR_RESOURCE_UTILS,
  RenderResourceFunc,
  ResourceCommandMap,
  ResourceDialogState,
  ADD_RESOURCE_EMBED
} from "../../lib/ckeditor/plugins/constants"
import ResourcePickerDialog from "./ResourcePickerDialog"

export interface Props {
  value?: string
  name?: string
  onChange?: (event: { target: { value: string; name: string } }) => void
  children?: React.ReactNode
  minimal?: boolean
  attach?: string
}

type RenderQueueEntry = [string, HTMLElement]

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
  const [resourcePickerState, setResourcePickerState] = useState<
    ResourceDialogState
  >("closed")

  const addResourceEmbed = useCallback(
    (uuid: string, variant: CKEResourceNodeType) => {
      if (editor.current) {
        editor.current.execute(ResourceCommandMap[variant], uuid)
        // @ts-ignore
        editor.current.editing.view.focus()
      }
    },
    [editor]
  )

  const [renderQueue, setRenderQueue] = useState<RenderQueueEntry[]>([])

  const renderResource: RenderResourceFunc = useCallback(
    (uuid: string, el: HTMLElement) => {
      setRenderQueue(xs => [...xs, [uuid, el]])
    },
    [setRenderQueue]
  )

  const openResourcePicker = useCallback(
    (resourceDialogType: CKEResourceNodeType) => {
      setResourcePickerState(resourceDialogType)
    },
    [setResourcePickerState]
  )

  const hasAttach = attach && attach.length > 0

  const editorConfig = useMemo(() => {
    if (minimal) {
      return MinimalEditorConfig
    } else {
      // this render function is stuck into the editor config
      // our ResourceEmbed plugin can pull the callback out,
      // and then use it to render resources within the editor.
      return {
        ...FullEditorConfig,
        [CKEDITOR_RESOURCE_UTILS]: {
          renderResource,
          openResourcePicker
        },
        toolbar: {
          ...FullEditorConfig.toolbar,
          items: FullEditorConfig.toolbar.items.filter(item =>
            hasAttach ?
              true :
              item !== ADD_RESOURCE_LINK && item !== ADD_RESOURCE_EMBED
          )
        }
      }
    }
  }, [minimal, renderResource, openResourcePicker, hasAttach])

  const onChangeCB = useCallback(
    (_event: any, editor: any) => {
      const data = editor.getData()
      if (onChange) {
        onChange({ target: { name: name ?? "", value: data } })
      }

      // we have to do some manual 'garbage collection' of a sort here
      // CKEditor doesn't delete nodes but just removes them from the editor
      // so if we don't clean up this list we'll keep rendering our EmbeddedResource
      // component into a bunch of detached DOM nodes and get a memory leak.
      //
      // filtering the queue to only dom nodes which are contained within document.body
      // should retain any nodes corresponding to resources currently in the editor
      // and remove those corresponding to what the user has deleted.
      setRenderQueue(xs => xs.filter(entry => document.body.contains(entry[1])))
    },
    [onChange, setRenderQueue, name]
  )

  const closeResourcePicker = useCallback(() => {
    setResourcePickerState("closed")
  }, [setResourcePickerState])

  return (
    <>
      <CKEditor
        editor={ClassicEditor}
        config={editorConfig}
        data={value ?? ""}
        onReady={setEditorRef}
        onChange={onChangeCB}
      />
      {hasAttach ? (
        <ResourcePickerDialog
          state={resourcePickerState}
          closeDialog={closeResourcePicker}
          insertEmbed={addResourceEmbed}
          attach={attach as string}
        />
      ) : null}
      {renderQueue.map(([uuid, el], idx) => (
        <EmbeddedResource key={`${uuid}_${idx}`} uuid={uuid} el={el} />
      ))}
    </>
  )
}
