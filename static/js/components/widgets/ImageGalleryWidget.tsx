import React, { useCallback, useEffect, useMemo, useRef, useState } from "react"
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
import { equals } from "ramda"

import { useWebsite } from "../../context/Website"
import { useWebsiteContent } from "../../hooks/websites"
import { siteContentRerouteUrl } from "../../lib/urls"
import { ImageGalleryHandle } from "../../lib/ckeditor/plugins/constants"
import { parseGalleryItem } from "../../lib/ckeditor/plugins/galleryItems"

interface Props {
  el: HTMLElement
  handle: ImageGalleryHandle
}

interface GalleryEntry {
  /** Stable while items move, and unique even when an image appears twice. */
  key: string
  /** The item's raw params, written back untouched. */
  raw: string
  uuid?: string
  href?: string
}

/**
 * dnd-kit needs an id for each item that stays the same while items move. An
 * image can appear twice in one gallery, so its uuid (or href) alone is not
 * unique; counting the earlier items that share it makes it so.
 */
const toEntries = (items: string[]): GalleryEntry[] => {
  const seen = new Map<string, number>()
  return items.map((raw) => {
    const { uuid, href } = parseGalleryItem(raw)
    const base = uuid || href || "item"
    const count = seen.get(base) ?? 0
    seen.set(base, count + 1)
    return { key: `${base}#${count}`, raw, uuid, href }
  })
}

/**
 * Display and edit component for image galleries embedded in the Markdown
 * editor.
 *
 * Like EmbeddedResource this renders into a raw element owned by CKEditor via a
 * portal, but unlike EmbeddedResource it also *writes* — reordering and
 * removing images go back into the CKEditor model through `handle`, so they
 * participate in undo/redo and mark the form dirty. Items move as their raw
 * param text, so params the editor knows nothing about are kept.
 *
 * Per-image metadata (alt text, caption, credit) is deliberately not editable
 * here. It lives on the image resource itself, which is the single source of
 * truth; each thumbnail links out to that resource's form.
 */
function ImageGalleryWidget(props: Props): JSX.Element {
  const { el, handle } = props

  const [items, setItems] = useState<string[]>(() => handle.getItems())
  const entries = useMemo(() => toEntries(items), [items])

  /**
   * The editingDowncast converter does not opt into reconversion, so this view
   * is never rebuilt when the gallery changes. Subscribing to the model instead
   * keeps the grid current — including after an undo — without remounting the
   * React tree mid-drag. Every change to the editor's data arrives here,
   * keystrokes elsewhere included, so state only changes when this gallery's
   * items have.
   */
  useEffect(
    () =>
      handle.onModelChange(() => {
        const next = handle.getItems()
        setItems((current) => (equals(current, next) ? current : next))
      }),
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
      const oldIndex = entries.findIndex((entry) => entry.key === active.id)
      const newIndex = entries.findIndex((entry) => entry.key === over.id)
      if (oldIndex === -1 || newIndex === -1) {
        return
      }
      handle.setItems(arrayMove(items, oldIndex, newIndex))
    },
    [entries, items, handle],
  )

  const galleryRef = useRef<HTMLDivElement>(null)
  const addButtonRef = useRef<HTMLButtonElement>(null)
  /** The position of the item just removed, until focus has moved on. */
  const removedIndex = useRef<number | null>(null)

  const removeItem = useCallback(
    (key: string) => {
      removedIndex.current = entries.findIndex((entry) => entry.key === key)
      handle.setItems(
        entries.filter((entry) => entry.key !== key).map((entry) => entry.raw),
      )
    },
    [entries, handle],
  )

  /**
   * Removing an item unmounts its remove button, which usually has focus.
   * Focus goes to the button that takes its place, else the one before it,
   * else "Add images", so a keyboard user keeps their place, and an undo
   * shortcut still comes from inside the gallery, where the plugin handles it.
   */
  useEffect(() => {
    const index = removedIndex.current
    if (index === null) {
      return
    }
    removedIndex.current = null
    const removeButtons = galleryRef.current?.querySelectorAll<HTMLElement>(
      ".image-gallery-item-remove",
    )
    const next = removeButtons?.length
      ? removeButtons[Math.min(index, removeButtons.length - 1)]
      : addButtonRef.current
    next?.focus()
  }, [entries])

  return createPortal(
    // CKEditor ignores DOM events from in here (the plugin marks the wrapper
    // data-cke-ignore-events), so mouse and keyboard reach these controls.
    <div className="image-gallery-editor" ref={galleryRef}>
      <div className="d-flex align-items-center justify-content-between mb-2">
        <h3 className="m-0">Image Gallery</h3>
        <button
          type="button"
          className="btn cyan-button"
          onClick={handle.openPicker}
          ref={addButtonRef}
        >
          Add images
        </button>
      </div>
      {entries.length === 0 ? (
        <div className="image-gallery-empty text-gray font-italic">
          No images yet — use “Add images” to choose some.
        </div>
      ) : (
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={handleDragEnd}
        >
          <SortableContext
            items={entries.map((entry) => entry.key)}
            strategy={rectSortingStrategy}
          >
            <div className="image-gallery-grid">
              {entries.map((entry) => (
                <GalleryThumbnail
                  key={entry.key}
                  entry={entry}
                  removeItem={removeItem}
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

/**
 * MarkdownEditor re-renders on every change to the editor, keystrokes
 * included. A gallery's element and handle stay the same for its lifetime, so
 * those re-renders stop here; the gallery's own changes arrive through
 * `onModelChange`.
 */
export default React.memo(ImageGalleryWidget)

interface ThumbnailProps {
  entry: GalleryEntry
  removeItem: (key: string) => void
}

function GalleryThumbnail(props: ThumbnailProps): JSX.Element {
  const { entry, removeItem } = props

  const { attributes, listeners, setNodeRef, transform, transition } =
    useSortable({ id: entry.key })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  }

  const onRemove = useCallback(
    () => removeItem(entry.key),
    [removeItem, entry.key],
  )

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
        <button
          type="button"
          className="material-icons gray-button hover ml-auto image-gallery-item-remove"
          title="Remove from gallery"
          aria-label="Remove from gallery"
          onClick={onRemove}
        >
          remove_circle_outline
        </button>
      </div>
      {entry.uuid ? (
        <LinkedImage uuid={entry.uuid} />
      ) : (
        <UnlinkedImage href={entry.href} />
      )}
    </div>
  )
}

function LinkedImage(props: { uuid: string }): JSX.Element {
  const { uuid } = props
  const website = useWebsite()
  const [resource, request] = useWebsiteContent(uuid)

  let placeholder = "Loading…"
  if (resource) {
    placeholder = "Not an image"
  } else if (request.isFinished) {
    // The request is done and returned nothing, e.g. the image was deleted.
    placeholder = "Image not found"
  }

  return (
    <>
      {resource?.file ? (
        <img className="img-fluid" src={resource.file} alt="" />
      ) : (
        <div className="image-gallery-item-missing text-gray">
          {placeholder}
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
    </>
  )
}

/**
 * An item with no uuid predates uuids being recorded on gallery items, and
 * the image_gallery_item_uuid cleanup could not match it to a resource. It
 * still renders on the site from its href, and stays exactly as authored.
 */
function UnlinkedImage(props: { href?: string }): JSX.Element {
  const { href } = props
  return (
    <>
      <div className="image-gallery-item-missing text-gray">
        Not linked to a resource
      </div>
      <span className="image-gallery-item-title">{href ?? "No file"}</span>
    </>
  )
}
