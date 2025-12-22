import React from "react"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import SortableItem from "./SortableItem"

jest.mock("@dnd-kit/sortable", () => ({
  useSortable: () => ({
    attributes: {},
    listeners: {},
    setNodeRef: jest.fn(),
    transform: null,
    transition: null,
  }),
}))

describe("SortableItem", () => {
  let deleteStub: jest.Mock<any, any>

  const renderItem = () =>
    render(
      <SortableItem
        deleteItem={deleteStub}
        item="item-id"
        id="item-id"
        title="A TITLE"
      />,
    )

  beforeEach(() => {
    deleteStub = jest.fn()
  })

  it("should display the title and a drag handle", () => {
    renderItem()
    expect(screen.getByText("drag_indicator")).toBeInTheDocument()
    expect(screen.getByText("A TITLE")).toBeInTheDocument()
  })

  it("should include a delete button", async () => {
    const user = userEvent.setup()
    renderItem()
    const deleteButton = screen.getByText("remove_circle_outline")
    expect(deleteButton).toBeInTheDocument()
    await user.click(deleteButton)
    expect(deleteStub).toHaveBeenCalledWith("item-id")
  })
})
