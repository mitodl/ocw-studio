import React from "react"
import { screen, waitFor, within, act } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import MenuField, { HugoItem, SortableMenuItem } from "./MenuField"

import { WebsiteContent } from "../../types/websites"
import { makeWebsiteContentDetail } from "../../util/factories/websites"
import IntegrationTestHelper from "../../testing_utils/IntegrationTestHelper"

let capturedOnChange: ((params: { items: SortableMenuItem[] }) => void) | null =
  null
jest.mock("react-nestable", () => {
  return {
    __esModule: true,
    default: ({
      items,
      renderItem,
      onChange,
    }: {
      items: SortableMenuItem[]
      renderItem: (props: { item: SortableMenuItem }) => React.ReactNode
      onChange: (params: { items: SortableMenuItem[] }) => void
    }) => {
      capturedOnChange = onChange
      return (
        <div data-testid="nestable-mock">
          {items.map((item) => (
            <div key={item.id} className="nestable-item">
              {renderItem({ item })}
              {item.children?.map((child) => (
                <div key={child.id} className="nestable-item">
                  {renderItem({ item: child })}
                  {child.children?.map((grandchild) => (
                    <div key={grandchild.id} className="nestable-item">
                      {renderItem({ item: grandchild })}
                    </div>
                  ))}
                </div>
              ))}
            </div>
          ))}
        </div>
      )
    },
  }
})

const dummyHugoItems: HugoItem[] = [
  {
    identifier: "32629a02-3dc5-4128-8e43-0392b51e7b61",
    name: "Unit 1",
    weight: 10,
  },
  {
    identifier: "32629a02-3dc5-4128-8e43-0392b51e7b62",
    name: "Unit 1 - Subunit 1",
    weight: 10,
    parent: "32629a02-3dc5-4128-8e43-0392b51e7b61",
  },
  {
    identifier: "32629a02-3dc5-4128-8e43-0392b51e7b63",
    name: "Unit 1 - Sub-subunit 1",
    weight: 10,
    parent: "32629a02-3dc5-4128-8e43-0392b51e7b62",
  },
]

describe("MenuField", () => {
  let helper: IntegrationTestHelper,
    onChangeStub: jest.Mock,
    contentContext: WebsiteContent[]
  const fieldName = "mymenu"

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    onChangeStub = jest.fn()
    contentContext = [
      {
        ...makeWebsiteContentDetail(),
        title: "Content Item 1",
        text_id: "content-1",
      },
      {
        ...makeWebsiteContentDetail(),
        title: "Content Item 2",
        text_id: "content-2",
      },
    ]
  })

  afterEach(() => {
    jest.restoreAllMocks()
  })

  const renderMenuField = (props = {}) =>
    helper.renderWithWebsite(
      <MenuField
        onChange={onChangeStub}
        name={fieldName}
        value={dummyHugoItems}
        contentContext={contentContext}
        {...props}
      />,
    )

  it("should render correctly on load", () => {
    renderMenuField()
    expect(screen.getByText("Unit 1")).toBeInTheDocument()
  })

  it("should render individual items", () => {
    renderMenuField()
    expect(screen.getByText("Unit 1")).toBeInTheDocument()
    expect(screen.getByText("Unit 1 - Subunit 1")).toBeInTheDocument()
    expect(screen.getByText("Unit 1 - Sub-subunit 1")).toBeInTheDocument()
    const settingsButtons = screen.getAllByText("settings")
    const deleteButtons = screen.getAllByText("delete")
    expect(settingsButtons.length).toBe(3)
    expect(deleteButtons.length).toBe(3)
  })

  it("should show a form to add new menu items", async () => {
    const user = userEvent.setup()
    const [{ unmount }] = renderMenuField()

    const addButton = screen.getByRole("button", { name: /add new/i })
    await user.click(addButton)

    expect(screen.getByText("Add Navigation Item")).toBeInTheDocument()
    expect(screen.getByLabelText(/title/i)).toBeInTheDocument()

    unmount()
  })

  it("provides a button to remove each individual menu item", async () => {
    const user = userEvent.setup()
    const [{ unmount }] = renderMenuField()

    const deleteButtons = screen.getAllByText("delete")
    expect(deleteButtons.length).toBeGreaterThan(0)

    await user.click(deleteButtons[0])

    const removeDialog = screen.getByRole("dialog")
    expect(removeDialog).toBeInTheDocument()

    const acceptButton = screen.getByRole("button", { name: /remove/i })
    await user.click(acceptButton)

    await waitFor(() => {
      expect(screen.queryByText("Unit 1")).not.toBeInTheDocument()
    })

    unmount()
  })

  it("should put an appropriate title on the modal", async () => {
    const user = userEvent.setup()

    const [{ unmount: unmount1 }] = renderMenuField()
    const addButton = screen.getByRole("button", { name: /add new/i })
    await user.click(addButton)
    expect(screen.getByText("Add Navigation Item")).toBeInTheDocument()
    unmount1()

    const [{ unmount: unmount2 }] = renderMenuField()
    const settingsButtons = screen.getAllByText("settings")
    await user.click(settingsButtons[0])
    expect(screen.getByText("Edit Navigation Item")).toBeInTheDocument()
    unmount2()
  })

  it("should show a form to edit existing menu items", async () => {
    const user = userEvent.setup()
    const [{ unmount }] = renderMenuField()

    const settingsButtons = screen.getAllByText("settings")
    await user.click(settingsButtons[0])

    expect(screen.getByText("Edit Navigation Item")).toBeInTheDocument()
    const titleInput = screen.getByLabelText(/title/i)
    expect(titleInput).toHaveValue("Unit 1")

    unmount()
  })

  it("menu item form should correctly update widget value with new menu item link", async () => {
    const user = userEvent.setup()
    const initialMenuItemCount = dummyHugoItems.length
    const contentItem = contentContext[0]

    jest.spyOn(global, "fetch").mockResolvedValue({
      json: () =>
        Promise.resolve({
          results: contentContext,
          count: contentContext.length,
          next: null,
          previous: null,
        }),
    } as Response)

    const [{ unmount }] = renderMenuField()

    const addButton = screen.getByRole("button", { name: /add new/i })
    await user.click(addButton)

    const titleInput = screen.getByLabelText(/title/i)
    await user.clear(titleInput)
    await user.type(titleInput, "My Title")

    const selectContainer = screen.getByText("Link to:").parentElement!
    const selectInput = within(selectContainer).getByRole("textbox")
    await user.click(selectInput)

    await waitFor(() => {
      expect(screen.getByText(contentItem.title!)).toBeInTheDocument()
    })
    await user.click(screen.getByText(contentItem.title!))

    const submitButton = screen.getByRole("button", { name: /save/i })
    await user.click(submitButton)

    await waitFor(() => {
      expect(onChangeStub).toHaveBeenCalled()
    })

    const updatedHugoMenuItems = onChangeStub.mock.calls[0][0].target.value
    expect(updatedHugoMenuItems).toHaveLength(initialMenuItemCount + 1)
    const newItem = updatedHugoMenuItems.find(
      (item: HugoItem) => item.name === "My Title",
    )
    expect(newItem).toBeDefined()

    unmount()
  })

  it("menu item form should correctly update widget value with existing menu item link", async () => {
    const user = userEvent.setup()
    const initialMenuItemCount = dummyHugoItems.length
    const [{ unmount }] = renderMenuField()

    const settingsButtons = screen.getAllByText("settings")
    await user.click(settingsButtons[1])

    const titleInput = screen.getByLabelText(/title/i)
    await user.clear(titleInput)
    await user.type(titleInput, "Updated Title")

    const submitButton = screen.getByRole("button", { name: /save/i })
    await user.click(submitButton)

    await waitFor(() => {
      expect(onChangeStub).toHaveBeenCalled()
    })

    const updatedHugoMenuItems = onChangeStub.mock.calls[0][0].target.value
    expect(updatedHugoMenuItems).toHaveLength(initialMenuItemCount)
    const updatedItem = updatedHugoMenuItems.find(
      (item: HugoItem) => item.name === "Updated Title",
    )
    expect(updatedItem).toBeDefined()
    expect(updatedItem.parent).toBe("32629a02-3dc5-4128-8e43-0392b51e7b61")

    unmount()
  })

  it("should pass the correct reorder function to the nestable component", () => {
    const dummyContentMenuItems: SortableMenuItem[] = [
      {
        id: "32629a02-3dc5-4128-8e43-0392b51e7b61",
        text: "Unit 1",
        children: [
          {
            id: "32629a02-3dc5-4128-8e43-0392b51e7b62",
            text: "Unit 1 - Subunit 1",
            children: [
              {
                id: "32629a02-3dc5-4128-8e43-0392b51e7b63",
                text: "Unit 1 - Sub-subunit 1",
                children: [],
                targetContentId: "32629a02-3dc5-4128-8e43-0392b51e7b63",
                targetUrl: null,
              },
            ],
            targetContentId: "32629a02-3dc5-4128-8e43-0392b51e7b62",
            targetUrl: null,
          },
        ],
        targetContentId: "32629a02-3dc5-4128-8e43-0392b51e7b61",
        targetUrl: null,
      },
    ]

    const [{ unmount }] = renderMenuField()

    const updatedMenuItems = [dummyContentMenuItems[0]]
    expect(capturedOnChange).not.toBeNull()
    act(() => {
      capturedOnChange!({ items: updatedMenuItems })
    })

    expect(onChangeStub).toHaveBeenCalledTimes(1)
    expect(onChangeStub.mock.calls[0][0].target.value).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          identifier: "32629a02-3dc5-4128-8e43-0392b51e7b61",
          name: "Unit 1",
        }),
      ]),
    )

    unmount()
  })
})
