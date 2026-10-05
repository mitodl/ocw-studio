import React from "react"
import { act, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import ImageGalleryWidget from "./ImageGalleryWidget"
import { IntegrationTestHelper } from "../../testing_utils"
import * as contextWebsite from "../../context/Website"
import {
  makeWebsiteContentDetail,
  makeWebsiteDetail,
} from "../../util/factories/websites"
import { Website, WebsiteContent } from "../../types/websites"
import { siteApiContentDetailUrl } from "../../lib/urls"
import { ImageGalleryHandle } from "../../lib/ckeditor/plugins/constants"

jest.mock("../../context/Website")
const useWebsite = jest.mocked(contextWebsite.useWebsite)

/**
 * The real DndContext portals its screen-reader nodes into document.body,
 * which test_setup.ts empties before Testing Library unmounts, so React then
 * fails to remove them. Stand-ins as in SortableSelect.test.tsx, which also
 * expose what a drag would report: the sortable ids and the onDragEnd handler,
 * and count thumbnail renders, since each thumbnail calls useSortable once.
 */
let dragEnd: (event: any) => void,
  sortableIds: string[],
  thumbnailRenders = 0
jest.mock("@dnd-kit/core", () => ({
  ...jest.requireActual("@dnd-kit/core"),
  DndContext: ({
    children,
    onDragEnd,
  }: {
    children: React.ReactNode
    onDragEnd: (event: any) => void
  }) => {
    dragEnd = onDragEnd
    return <>{children}</>
  },
}))
jest.mock("@dnd-kit/sortable", () => ({
  ...jest.requireActual("@dnd-kit/sortable"),
  SortableContext: ({
    children,
    items,
  }: {
    children: React.ReactNode
    items: string[]
  }) => {
    sortableIds = items
    return <>{children}</>
  },
  useSortable: () => {
    thumbnailRenders++
    return {
      attributes: {},
      listeners: {},
      setNodeRef: jest.fn(),
      transform: null,
      transition: null,
    }
  },
}))

describe("ImageGalleryWidget", () => {
  let helper: IntegrationTestHelper,
    website: Website,
    image: WebsiteContent,
    el: HTMLElement

  const makeHandle = (items: string[]) => ({
    getItems: () => items,
    setItems: jest.fn(),
    onModelChange: () => () => undefined,
    openPicker: jest.fn(),
  })

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    website = makeWebsiteDetail()
    image = { ...makeWebsiteContentDetail(), file: "/courses/x/pyrite.jpg" }
    useWebsite.mockReturnValue(website)
    helper.mockGetRequest(
      siteApiContentDetailUrl
        .param({ name: website.name, textId: image.text_id })
        .toString(),
      image,
    )
    el = document.createElement("div")
    document.body.appendChild(el)
  })

  afterEach(() => {
    document.body.removeChild(el)
  })

  const renderWidget = (handle: ImageGalleryHandle) =>
    helper.render(<ImageGalleryWidget el={el} handle={handle} />)

  it("shows an item that is not linked to a resource by its href", async () => {
    renderWidget(
      makeHandle([
        ` uuid="${image.text_id}" href="pyrite.jpg" text="Pyrite" `,
        ' href="legacy.jpg" data-ngdesc="" text="Old" ',
      ]),
    )
    await waitFor(() => {
      expect(screen.getByText(image.title!)).toBeInTheDocument()
    })
    expect(screen.getAllByText("Not linked to a resource")).toHaveLength(1)
    expect(screen.getByText("legacy.jpg")).toBeInTheDocument()
  })

  it("removes only the item clicked, leaving every other item's params as they were", async () => {
    const user = userEvent.setup()
    const linked = ` uuid="${image.text_id}" href="pyrite.jpg" text="Pyrite" `
    const legacy = ' href="legacy.jpg" data-ngdesc="" text="Old" '
    const handle = makeHandle([linked, linked, legacy])
    renderWidget(handle)

    await user.click(screen.getAllByTitle("Remove from gallery")[1])

    expect(handle.setItems).toHaveBeenCalledWith([linked, legacy])
  })

  it("lets a keyboard user remove an item", async () => {
    const user = userEvent.setup()
    const linked = ` uuid="${image.text_id}" href="pyrite.jpg" text="Pyrite" `
    const legacy = ' href="legacy.jpg" data-ngdesc="" text="Old" '
    const handle = makeHandle([linked, legacy])
    renderWidget(handle)

    screen.getAllByRole("button", { name: "Remove from gallery" })[0].focus()
    await user.keyboard("{Enter}")

    expect(handle.setItems).toHaveBeenCalledWith([legacy])
  })

  it("keeps a keyboard user's place in the gallery as they remove items", async () => {
    const user = userEvent.setup()
    // Items change when set, and subscribers hear of it, as with the plugin.
    let items = [' href="a.jpg" ', ' href="b.jpg" ', ' href="c.jpg" ']
    const listeners = new Set<() => void>()
    renderWidget({
      getItems: () => items,
      setItems: (next) => {
        items = next
        listeners.forEach((listener) => listener())
      },
      onModelChange: (listener) => {
        listeners.add(listener)
        return () => listeners.delete(listener)
      },
      openPicker: jest.fn(),
    })
    const removeButtons = () =>
      screen.getAllByRole("button", { name: "Remove from gallery" })

    removeButtons()[1].focus()
    await user.keyboard("{Enter}")
    // c.jpg has taken b.jpg's place, and so has focus.
    expect(screen.queryByText("b.jpg")).not.toBeInTheDocument()
    expect(removeButtons()[1]).toHaveFocus()

    await user.keyboard("{Enter}")
    // With nothing after it, the item before it.
    expect(screen.getByText("a.jpg")).toBeInTheDocument()
    expect(removeButtons()[0]).toHaveFocus()

    await user.keyboard("{Enter}")
    expect(screen.getByRole("button", { name: "Add images" })).toHaveFocus()
  })

  it("skips re-rendering for a model change that leaves its items as they were", () => {
    const items = [' href="a.jpg" ', ' href="b.jpg" ']
    let notify: () => void = () => undefined
    renderWidget({
      // A fresh array each time, as the plugin parses it from the model.
      getItems: () => [...items],
      setItems: jest.fn(),
      onModelChange: (listener) => {
        notify = listener
        return () => undefined
      },
      openPicker: jest.fn(),
    })
    thumbnailRenders = 0

    // E.g. a keystroke elsewhere in the editor.
    act(() => notify())

    expect(thumbnailRenders).toBe(0)
  })

  it("skips re-rendering when its parent re-renders with the same gallery", () => {
    const handle = makeHandle([' href="a.jpg" ', ' href="b.jpg" '])
    let rerenderParent: () => void = () => undefined
    // As MarkdownEditor does on every change to the editor.
    const Parent = () => {
      const [, setCount] = React.useState(0)
      rerenderParent = () => setCount((count) => count + 1)
      return <ImageGalleryWidget el={el} handle={handle} />
    }
    helper.render(<Parent />)
    thumbnailRenders = 0

    act(() => rerenderParent())

    expect(thumbnailRenders).toBe(0)
  })

  it("moves a dragged item's raw params to where it was dropped", () => {
    const first = ` uuid="${image.text_id}" href="pyrite.jpg" text="Pyrite" `
    const second = ' href="legacy.jpg" data-ngdesc="" text="Old" '
    const third = ' href="quartz.jpg" text="Quartz" '
    const handle = makeHandle([first, second, third])
    renderWidget(handle)

    dragEnd({ active: { id: sortableIds[0] }, over: { id: sortableIds[2] } })

    expect(handle.setItems).toHaveBeenCalledWith([second, third, first])
  })
})
