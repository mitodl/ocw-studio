import React from "react"
import { shallow } from "enzyme"

import SortableWebsiteCollectionItem from "./SortableWebsiteCollectionItem"
import { WebsiteCollectionItem } from "../types/website_collections"
import { makeWebsiteCollectionItem } from "../util/factories/website_collections"

describe("SortableWebsiteCollectionItem", () => {
  let item: WebsiteCollectionItem, deleteStub: jest.Mock<any, any>

  const renderItem = () =>
    shallow(
      <SortableWebsiteCollectionItem
        deleteItem={deleteStub}
        item={item}
        id={String(item.id)}
      />
    )

  beforeEach(() => {
    item = makeWebsiteCollectionItem()
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
    expect(wrapper.find(".title").text()).toBe(item.website_title)
  })

  it("should include a delete button", () => {
    const wrapper = renderItem()
    const deleteButton = wrapper.find(".material-icons").at(1)
    expect(deleteButton.text()).toBe("remove_circle_outline")
    deleteButton.simulate("click")
    expect(deleteStub).toBeCalledWith(item)
  })
})
