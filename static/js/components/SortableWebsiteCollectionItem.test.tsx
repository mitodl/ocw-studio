import React from "react"
import { shallow } from "enzyme"

import SortableWebsiteCollectionItem from "./SortableWebsiteCollectionItem"
import { WebsiteCollectionItem } from "../types/website_collections"
import { makeWebsiteCollectionItem } from "../util/factories/website_collections"

describe("SortableWebsiteCollectionItem", () => {
  let item: WebsiteCollectionItem

  const renderItem = () =>
    shallow(<SortableWebsiteCollectionItem item={item} id={String(item.id)} />)

  beforeEach(() => {
    item = makeWebsiteCollectionItem()
  })

  it("should display the title and a drag handle", () => {
    const wrapper = renderItem()
    expect(wrapper.find(".material-icons").text()).toBe("drag_indicator")
    expect(wrapper.find(".title").text()).toBe(item.website_title)
  })
})
