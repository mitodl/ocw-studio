import React, { useCallback, useEffect, useState } from "react"
import { createPortal } from "react-dom"
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
} from "@dnd-kit/core"
import {
  SortableContext,
  arrayMove,
  rectSortingStrategy,
  sortableKeyboardCoordinates,
  useSortable,
} from "@dnd-kit/sortable"
import { CSS } from "@dnd-kit/utilities"

import { useWebsite } from "../../context/Website"
import { useWebsiteContent } from "../../hooks/websites"
import { siteContentRerouteUrl } from "../../lib/urls"
import { ImageGalleryHandle } from "../../lib/ckeditor/plugins/constants"

interface Props {
  el: HTMLElement
  handle: ImageGalleryHandle
}

/**
 * Display and edit component for image galleries embedded in the Markdown
 * editor.
 *
 * Like EmbeddedResource this renders into a raw element owned by CKEditor via a
 * portal, but unlike EmbeddedResource it also *writes* — reordering and
 * removing images go back into the CKEditor model through `handle`, so they
 * participate in undo/redo and mark the form dirty.
 *
 * Per-image metadata (alt text, caption, credit) is deliberately not editable
 * here. It lives on the image resource itself, which is the single source of
 * truth; each thumbnail links out to that resource's form.
 */
export default function ImageGalleryWidget(props: Props): JSX.Element {
  const { el, handle } = props

  const [uuids, setUuids] = useState<string[]>(() => handle.getUuids())

  /**
   * The editingDowncast converter does not opt into reconversion, so this view
   * is never rebuilt when the gallery changes. Subscribing to the model instead
   * keeps the grid current — including after an undo — without remounting the
   * React tree mid-drag.
   */
  useEffect(
    () => handle.onModelChange(() => setUuids(handle.getUuids())),
    [handle],
  )

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    }),
  )

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      const { active, over } = event
      if (!over || active.id === over.id) {
        return
      }
      const oldIndex = uuids.indexOf(String(active.id))
      const newIndex = uuids.indexOf(String(over.id))
      if (oldIndex === -1 || newIndex === -1) {
        return
      }
      handle.setUuids(arrayMove(uuids, oldIndex, newIndex))
    },
    [uuids, handle],
  )

  const removeImage = useCallback(
    (uuid: string) => {
      handle.setUuids(uuids.filter((item) => item !== uuid))
    },
    [uuids, handle],
  )

  return createPortal(
    <div
      className="image-gallery-editor"
      /**
       * CKEditor's widget layer binds mousedown on the widget in order to
       * select it, which would otherwise swallow the drag handles and buttons
       * below. The gallery's interior is ours, so keep those events local.
       */
      onMouseDown={(event) => event.stopPropagation()}
    >
      <div className="d-flex align-items-center justify-content-between mb-2">
        <h3 className="m-0">Image Gallery</h3>
        <button
          type="button"
          className="btn cyan-button"
          onClick={handle.openPicker}
        >
          Add images
        </button>
      </div>
      {uuids.length === 0 ? (
        <div className="image-gallery-empty text-gray font-italic">
          No images yet — use “Add images” to choose some.
        </div>
      ) : (
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={handleDragEnd}
        >
          <SortableContext items={uuids} strategy={rectSortingStrategy}>
            <div className="image-gallery-grid">
              {uuids.map((uuid) => (
                <GalleryThumbnail
                  key={uuid}
                  uuid={uuid}
                  removeImage={removeImage}
                />
              ))}
            </div>
          </SortableContext>
        </DndContext>
      )}
    </div>,
    el,
  )
}

interface ThumbnailProps {
  uuid: string
  removeImage: (uuid: string) => void
}

function GalleryThumbnail(props: ThumbnailProps): JSX.Element {
  const { uuid, removeImage } = props
  const website = useWebsite()
  const [resource] = useWebsiteContent(uuid)

  const { attributes, listeners, setNodeRef, transform, transition } =
    useSortable({ id: uuid })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  }

  const onRemove = useCallback(() => removeImage(uuid), [removeImage, uuid])

  return (
    <div
      className="image-gallery-item"
      ref={setNodeRef}
      // @ts-expect-error unavoidable because of the library's types, as in SortableItem
      style={style}
    >
      <div className="image-gallery-item-controls">
        <span
          className="material-icons drag-handle"
          title="Drag to reorder"
          {...attributes}
          {...listeners}
        >
          drag_indicator
        </span>
        <span
          className="material-icons gray-button hover ml-auto"
          title="Remove from gallery"
          onClick={onRemove}
        >
          remove_circle_outline
        </span>
      </div>
      {resource?.file ? (
        <img className="img-fluid" src={resource.file} alt="" />
      ) : (
        <div className="image-gallery-item-missing text-gray">
          {resource ? "Not an image" : "Loading…"}
        </div>
      )}
      <a
        className="image-gallery-item-title"
        href={siteContentRerouteUrl
          .param({ name: website.name, uuid })
          .toString()}
        target="_blank"
        rel="noopener noreferrer"
        title="Edit this image's caption, credit and alt text"
      >
        {resource?.title ?? uuid}
      </a>
    </div>
  )
}
