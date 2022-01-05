import React from "react"
import { shallow } from "enzyme"

import SortableItem from "./SortableItem"

describe("SortableItem", () => {
  let deleteStub: jest.Mock<any, any>

  const renderItem = () =>
    shallow(
      <SortableItem
        deleteItem={deleteStub}
        item="item-id"
        id="item-id"
        title="A TITLE"
      />
    )

  beforeEach(() => {
    deleteStub = jest.fn()
  })

  it("should display the title and a drag handle", () => {
    const wrapper = renderItem()
    expect(
      wrapper
        .find(".material-icons")
        .at(0)
        .text()
    ).toBe("drag_indicator")
    expect(wrapper.find(".title").text()).toBe("A TITLE")
  })

  it("should include a delete button", () => {
    const wrapper = renderItem()
    const deleteButton = wrapper.find(".material-icons").at(1)
    expect(deleteButton.text()).toBe("remove_circle_outline")
    deleteButton.simulate("click")
    expect(deleteStub).toBeCalledWith("item-id")
  })
})
