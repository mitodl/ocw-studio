import React, { useCallback, useMemo, useRef, useState } from "react"
import { CKEditor } from "@ckeditor/ckeditor5-react"
import { Editor } from "@ckeditor/ckeditor5-core"
import ClassicEditor from "@ckeditor/ckeditor5-editor-classic/src/classiceditor"
import CKEditorInspector from "@ckeditor/ckeditor5-inspector"

import {
  FullEditorConfig,
  MinimalEditorConfig,
  MinimalWithMathEditorConfig,
} from "../../lib/ckeditor/CKEditor"
import ResourceLink from "../../lib/ckeditor/plugins/ResourceLink"
import { checkNotSubAndSup } from "../../lib/ckeditor/attributeChecks"
import EmbeddedResource from "./EmbeddedResource"
import {
  ADD_RESOURCE_LINK,
  CKEResourceNodeType,
  CKEDITOR_RESOURCE_UTILS,
  RenderResourceFunc,
  RESOURCE_EMBED_COMMAND,
  ResourceDialogMode,
  ADD_RESOURCE_EMBED,
  RESOURCE_EMBED,
  RESOURCE_LINK,
  MARKDOWN_CONFIG_KEY,
  RESOURCE_LINK_CONFIG_KEY,
  WEBSITE_NAME,
  MINIMAL_WITH_MATH,
  IMAGE_GALLERY_COMMAND,
  ImageGalleryHandle,
  RenderGalleryFunc,
} from "../../lib/ckeditor/plugins/constants"
import ResourcePickerDialog, { TabIds } from "./ResourcePickerDialog"
import ImageGalleryWidget from "./ImageGalleryWidget"
import useThrowSynchronously from "../../hooks/useAsyncError"
import { useWebsite } from "../../context/Website"
import { ContentType } from "../../constants"
import { siteContentRerouteUrl } from "../../lib/urls"
import { useFeatureFlag } from "../../lib/util"
import { FEATURE_FLAG_CUSTOM_LINKUI } from "../../common/feature_flags"
import CustomLink from "../../lib/ckeditor/plugins/CustomLink"

export interface Props {
  value?: string
  name?: string
  onChange?: (event: { target: { value: string; name: string } }) => void
  children?: React.ReactNode
  minimal?: boolean | typeof MINIMAL_WITH_MATH
  embed: string[]
  link: string[]
  allowedHtml: string[]
}

type RenderQueueEntry = [string, HTMLElement]

type GalleryQueueEntry = [HTMLElement, ImageGalleryHandle]

/**
 * A component for editing Markdown using CKEditor.
 *
 * pass minimal: true to get a minimal version.
 */
export default function MarkdownEditor(props: Props): JSX.Element {
  const { link, embed, value, name, onChange, minimal, allowedHtml } = props
  const throwSynchronously = useThrowSynchronously()
  const website = useWebsite()

  const isCustomLinkUIEnabled = useFeatureFlag(FEATURE_FLAG_CUSTOM_LINKUI)

  const editor = useRef<Editor>()
  const onReady = useCallback((editorInstance: Editor) => {
    editor.current = editorInstance
    if (!editor.current) {
      /**
       * It is unclear to me why this happens.
       * It seems like when our MarkdownEditor opens, an editor is created,
       * immediately destroyed, onReady is called (with null), and then
       * re-created, and onReady is called again (with real editor)
       */
      return
    }
    if (process.env.NODE_ENV === "development") {
      CKEditorInspector.attach(editor)
    }
    editor.current.model.schema.addAttributeCheck(checkNotSubAndSup)
  }, [])

  const [resourcePickerMode, setResourcePickerMode] =
    useState<ResourceDialogMode>(RESOURCE_LINK)
  const [isResourcePickerOpen, setIsResourcePickerOpen] = useState(false)

  const addResourceEmbed = useCallback(
    (uuid: string, title: string, variant: CKEResourceNodeType) => {
      if (editor.current) {
        if (variant === "resourceLink") {
          // we pass the title down because we want to set that as the
          // default text in the link, in the case where we're not adding
          // the link attribute to existing text.
          const resourceLink = editor.current.plugins.get(ResourceLink)
          resourceLink.createResourceLink(uuid, title)
        } else {
          editor.current.execute(RESOURCE_EMBED_COMMAND, uuid)
        }

        editor.current.editing.view.focus()
      }
    },
    [],
  )

  const [renderQueue, setRenderQueue] = useState<RenderQueueEntry[]>([])

  const renderResource: RenderResourceFunc = useCallback(
    (uuid: string, el: HTMLElement) => {
      setRenderQueue((xs) => [...xs, [uuid, el]])
    },
    [setRenderQueue],
  )

  const openResourcePicker = useCallback(
    (resourceDialogType: CKEResourceNodeType) => {
      setIsGalleryPicker(false)
      setResourcePickerMode(resourceDialogType)
      setIsResourcePickerOpen(true)
    },
    [setResourcePickerMode, setIsResourcePickerOpen],
  )

  const [galleryQueue, setGalleryQueue] = useState<GalleryQueueEntry[]>([])

  const renderImageGallery: RenderGalleryFunc = useCallback(
    (el: HTMLElement, handle: ImageGalleryHandle) => {
      setGalleryQueue((xs) => [...xs, [el, handle]])
    },
    [setGalleryQueue],
  )

  /**
   * The gallery being added to, or null when the picker's selection should
   * become a brand new gallery.
   */
  const [galleryHandle, setGalleryHandle] = useState<ImageGalleryHandle | null>(
    null,
  )
  const [isGalleryPicker, setIsGalleryPicker] = useState(false)

  const openImageGalleryPicker = useCallback(
    (handle: ImageGalleryHandle | null) => {
      setGalleryHandle(handle)
      setIsGalleryPicker(true)
      setResourcePickerMode(RESOURCE_EMBED)
      setIsResourcePickerOpen(true)
    },
    [],
  )

  const addGalleryImages = useCallback(
    (uuids: string[]) => {
      if (galleryHandle) {
        // Appending to an existing gallery. Skip anything already present so a
        // re-pick cannot duplicate an image.
        const existing = galleryHandle.getUuids()
        galleryHandle.setUuids([
          ...existing,
          ...uuids.filter((uuid) => !existing.includes(uuid)),
        ])
      } else {
        editor.current?.execute(IMAGE_GALLERY_COMMAND, uuids)
      }
      editor.current?.editing.view.focus()
    },
    [galleryHandle],
  )

  const editorConfig = useMemo(() => {
    const toolbarItemsFilter = (item: string): boolean => {
      if (item === ADD_RESOURCE_LINK) {
        return link.length > 0
      }
      if (item === ADD_RESOURCE_EMBED) {
        return embed.length > 0
      }
      if (item === "superscript") {
        return allowedHtml.includes("sup")
      }
      if (item === "subscript") {
        return allowedHtml.includes("sub")
      }
      return true
    }
    const resourceLink = {
      [RESOURCE_LINK_CONFIG_KEY]: {
        hrefTemplate: `${location.origin}${
          siteContentRerouteUrl.param({
            name: website.name,
          }).pathname
        }`,
      },
      [WEBSITE_NAME]: website.name,
    }

    const baseConfig =
      minimal === MINIMAL_WITH_MATH
        ? MinimalWithMathEditorConfig
        : minimal
          ? MinimalEditorConfig
          : FullEditorConfig

    // Create a copy of plugins to avoid mutating the original
    const plugins = [...baseConfig.plugins]
    if (isCustomLinkUIEnabled) {
      plugins.push(CustomLink)
    }

    return {
      ...baseConfig,
      plugins,
      [CKEDITOR_RESOURCE_UTILS]: {
        renderResource,
        openResourcePicker,
        renderImageGallery,
        openImageGalleryPicker,
      },
      toolbar: {
        ...baseConfig.toolbar,
        items: baseConfig.toolbar.items.filter(toolbarItemsFilter),
      },
      [MARKDOWN_CONFIG_KEY]: {
        allowedHtml,
      },
      ...resourceLink,
    }
  }, [
    minimal,
    renderResource,
    openResourcePicker,
    renderImageGallery,
    openImageGalleryPicker,
    link,
    embed,
    allowedHtml,
    website.name,
    isCustomLinkUIEnabled,
  ])

  const configKey = useMemo(() => JSON.stringify(editorConfig), [editorConfig])

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
      setRenderQueue((xs) =>
        xs.filter((entry) => document.body.contains(entry[1])),
      )
      setGalleryQueue((xs) =>
        xs.filter((entry) => document.body.contains(entry[0])),
      )
    },
    [onChange, setRenderQueue, setGalleryQueue, name],
  )

  const closeResourcePicker = useCallback(() => {
    setIsResourcePickerOpen(false)
  }, [setIsResourcePickerOpen])

  return (
    <>
      <div key={configKey}>
        <CKEditor
          editor={ClassicEditor}
          config={editorConfig}
          data={value ?? ""}
          onReady={onReady}
          onChange={onChangeCB}
          onError={throwSynchronously}
        />
      </div>
      {(link.length > 0 || embed.length > 0 || isGalleryPicker) && (
        <ResourcePickerDialog
          isOpen={isResourcePickerOpen}
          mode={resourcePickerMode}
          contentNames={
            isGalleryPicker
              ? [ContentType.Resource]
              : resourcePickerMode === RESOURCE_LINK
                ? link
                : embed
          }
          closeDialog={closeResourcePicker}
          insertEmbed={addResourceEmbed}
          multiple={isGalleryPicker}
          insertMultiple={addGalleryImages}
          restrictToTabIds={isGalleryPicker ? [TabIds.Images] : undefined}
          dialogTitle={isGalleryPicker ? "Add Images to Gallery" : undefined}
          acceptLabel={isGalleryPicker ? "Add images" : undefined}
        />
      )}
      {renderQueue.map(([uuid, el], idx) => (
        <EmbeddedResource key={`${uuid}_${idx}`} uuid={uuid} el={el} />
      ))}
      {galleryQueue.map(([el, handle], idx) => (
        <ImageGalleryWidget key={`gallery_${idx}`} el={el} handle={handle} />
      ))}
    </>
  )
}
