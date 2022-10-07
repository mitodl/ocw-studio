import React, { useCallback, useMemo, useRef, useState } from "react"
import { CKEditor } from "@ckeditor/ckeditor5-react"
import { editor } from "@ckeditor/ckeditor5-core"
import ClassicEditor from "@ckeditor/ckeditor5-editor-classic/src/classiceditor"
import CKEditorInspector from "@ckeditor/ckeditor5-inspector"

import {
  FullEditorConfig,
  MinimalEditorConfig,
  insertResourceLink
} from "../../lib/ckeditor/CKEditor"
import EmbeddedResource from "./EmbeddedResource"
import {
  ADD_RESOURCE_LINK,
  CKEResourceNodeType,
  CKEDITOR_RESOURCE_UTILS,
  RenderResourceFunc,
  ResourceCommandMap,
  ResourceDialogMode,
  ADD_RESOURCE_EMBED,
  RESOURCE_LINK
} from "../../lib/ckeditor/plugins/constants"
import ResourcePickerDialog from "./ResourcePickerDialog"
import useThrowSynchronously from "../../hooks/useAsyncError"

export interface Props {
  value?: string
  name?: string
  onChange?: (event: { target: { value: string; name: string } }) => void
  children?: React.ReactNode
  minimal?: boolean
  embed: string[]
  link: string[]
}

type RenderQueueEntry = [string, HTMLElement]

/**
 * A component for editing Markdown using CKEditor.
 *
 * pass minimal: true to get a minimal version.
 */
export default function MarkdownEditor(props: Props): JSX.Element {
  const { link, embed, value, name, onChange, minimal } = props
  const throwSynchronously = useThrowSynchronously()

  const editor = useRef<editor.Editor>()
  const setEditorRef = useCallback(editorInstance => {
    editor.current = editorInstance
    if (process.env.NODE_ENV === "development" && editor.current) {
      CKEditorInspector.attach(editor)
    }
  }, [])

  const [resourcePickerMode, setResourcePickerMode] = useState<
    ResourceDialogMode
  >(RESOURCE_LINK)
  const [isResourcePickerOpen, setIsResourcePickerOpen] = useState(false)

  const addResourceEmbed = useCallback(
    (uuid: string, title: string, variant: CKEResourceNodeType) => {
      if (editor.current) {
        if (variant === "resourceLink") {
          // we pass the title down because we want to set that as the
          // default text in the link, in the case where we're not adding
          // the link attribute to existing text.
          insertResourceLink(editor.current, uuid, title)
        } else {
          editor.current.execute(ResourceCommandMap[variant], uuid)
        }

        editor.current.editing.view.focus()
      }
    },
    []
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
      setResourcePickerMode(resourceDialogType)
      setIsResourcePickerOpen(true)
    },
    [setResourcePickerMode, setIsResourcePickerOpen]
  )

  const editorConfig = useMemo(() => {
    const toolbarItemsFilter = (item: string): boolean => {
      if (item === ADD_RESOURCE_LINK) {
        return link.length > 0
      }
      if (item === ADD_RESOURCE_EMBED) {
        return embed.length > 0
      }
      return true
    }

    if (minimal) {
      return {
        ...MinimalEditorConfig,
        [CKEDITOR_RESOURCE_UTILS]: {
          renderResource,
          openResourcePicker
        },
        toolbar: {
          ...MinimalEditorConfig.toolbar,
          items: MinimalEditorConfig.toolbar.items.filter(toolbarItemsFilter)
        }
      }
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
          items: FullEditorConfig.toolbar.items.filter(toolbarItemsFilter)
        }
      }
    }
  }, [minimal, renderResource, openResourcePicker, link, embed])

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
    setIsResourcePickerOpen(false)
  }, [setIsResourcePickerOpen])

  return (
    <>
      <CKEditor
        editor={ClassicEditor}
        config={editorConfig}
        data={value ?? ""}
        onReady={setEditorRef}
        onChange={onChangeCB}
        onError={throwSynchronously}
      />
      {(link.length > 0 || embed.length > 0) && (
        <ResourcePickerDialog
          isOpen={isResourcePickerOpen}
          mode={resourcePickerMode}
          contentNames={resourcePickerMode === RESOURCE_LINK ? link : embed}
          closeDialog={closeResourcePicker}
          insertEmbed={addResourceEmbed}
        />
      )}
      {renderQueue.map(([uuid, el], idx) => (
        <EmbeddedResource key={`${uuid}_${idx}`} uuid={uuid} el={el} />
      ))}
    </>
  )
}
