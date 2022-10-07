import React from "react"
import { shallow } from "enzyme"
import MenuField, { HugoItem, InternalSortableMenuItem } from "./MenuField"
import { EXTERNAL_LINK_PREFIX } from "../../constants"

import { LinkType, WebsiteContent } from "../../types/websites"
import { makeWebsiteContentDetail } from "../../util/factories/websites"

const dummyHugoItems: HugoItem[] = [
  {
    identifier: "external-12345",
    name:       "External Link #1",
    url:        "http://example.com",
    weight:     20
  },
  {
    identifier: "32629a02-3dc5-4128-8e43-0392b51e7b61",
    name:       "Unit 1",
    weight:     10
  },
  {
    identifier: "32629a02-3dc5-4128-8e43-0392b51e7b62",
    name:       "Unit 1 - Subunit 1",
    weight:     10,
    parent:     "32629a02-3dc5-4128-8e43-0392b51e7b61"
  },
  {
    identifier: "32629a02-3dc5-4128-8e43-0392b51e7b63",
    name:       "Unit 1 - Sub-subunit 1",
    weight:     10,
    parent:     "32629a02-3dc5-4128-8e43-0392b51e7b62"
  }
]

const dummyInternalMenuItems: Required<InternalSortableMenuItem>[] = [
  {
    id:       "32629a02-3dc5-4128-8e43-0392b51e7b61",
    text:     "Unit 1",
    children: [
      {
        id:       "32629a02-3dc5-4128-8e43-0392b51e7b62",
        text:     "Unit 1 - Subunit 1",
        children: [
          {
            id:              "32629a02-3dc5-4128-8e43-0392b51e7b63",
            text:            "Unit 1 - Sub-subunit 1",
            children:        [],
            targetContentId: "32629a02-3dc5-4128-8e43-0392b51e7b63",
            targetUrl:       null
          }
        ],
        targetContentId: "32629a02-3dc5-4128-8e43-0392b51e7b62",
        targetUrl:       null
      }
    ],
    targetContentId: "32629a02-3dc5-4128-8e43-0392b51e7b61",
    targetUrl:       null
  },
  {
    id:              "external-12345",
    text:            "External Link #1",
    children:        [],
    targetContentId: null,
    targetUrl:       "http://example.com"
  }
]

describe("MenuField", () => {
  let render: any, onChangeStub: any, contentContext: WebsiteContent[]
  const fieldName = "mymenu"

  beforeEach(() => {
    onChangeStub = jest.fn()
    contentContext = [makeWebsiteContentDetail(), makeWebsiteContentDetail()]

    render = (props = {}) =>
      shallow(
        <MenuField
          onChange={onChangeStub}
          name={fieldName}
          value={dummyHugoItems}
          contentContext={contentContext}
          {...props}
        />
      )
  })

  const renderMenuItemForm = (menuItem: InternalSortableMenuItem | null) => {
    const wrapper = render()
    expect(wrapper.find("BasicModal").prop("isVisible")).toBe(false)
    const nestable = wrapper.find("Nestable")
    let formShowBtn
    if (menuItem) {
      const renderedMenuItem = shallow(
        nestable.prop("renderItem")({ item: menuItem })
      )
      formShowBtn = renderedMenuItem.find("button").at(0)
    } else {
      formShowBtn = wrapper.find("button.cyan-button")
    }
    const preventDefaultStub = jest.fn()
    formShowBtn.prop("onClick")({ preventDefault: preventDefaultStub })
    wrapper.update()
    if (menuItem) {
      expect(preventDefaultStub).toHaveBeenCalledTimes(1)
    }
    const itemFormPanel = wrapper.find("BasicModal")
    expect(itemFormPanel.prop("isVisible")).toBe(true)
    return itemFormPanel.dive().find("MenuItemForm")
  }

  it("should render correctly on load", () => {
    const wrapper = render()
    const nestable = wrapper.find("Nestable")
    expect(nestable.exists()).toBe(true)
    expect(nestable.prop("items")).toEqual(dummyInternalMenuItems)
  })

  it("should render individual items", () => {
    const wrapper = render()
    const nestable = wrapper.find("Nestable")
    const menuItem = dummyInternalMenuItems[0]
    const renderedMenuItem = shallow(
      nestable.prop("renderItem")({ item: menuItem })
    )
    expect(renderedMenuItem.find(".menu-title").text()).toEqual(menuItem.text)
    expect(renderedMenuItem.find("button").length).toEqual(2)
  })

  it("should pass the correct reorder function to the nestable component", () => {
    const updatedMenuItems = [dummyInternalMenuItems[0]]
    const wrapper = render()
    const nestable = wrapper.find("Nestable")
    nestable.prop("onChange")({ items: updatedMenuItems })
    wrapper.update()
    expect(wrapper.find("Nestable").prop("items")).toEqual(updatedMenuItems)
  })

  it("should show a form to add new menu items", () => {
    const menuItemForm = renderMenuItemForm(null)
    const formProps = menuItemForm.props()
    expect(formProps.activeItem).toEqual(null)
  })

  it("provides a button to remove each individual menu item", () => {
    const menuItem = dummyInternalMenuItems[0]
    const wrapper = render()
    const nestable = wrapper.find("Nestable")
    const renderedMenuItem = shallow(
      nestable.prop("renderItem")({ item: menuItem })
    )
    const deleteBtn = renderedMenuItem.find("button").at(1)
    expect(deleteBtn.exists()).toBe(true)
    expect(deleteBtn.prop("className")).toContain("material-icons")
    expect(deleteBtn.text()).toEqual("delete")
    const preventDefaultStub = jest.fn()
    // @ts-expect-error Not simulating the whole event
    deleteBtn.prop("onClick")({ preventDefault: preventDefaultStub })
    wrapper.update()
    expect(preventDefaultStub).toHaveBeenCalledTimes(1)
    const removeDialog = wrapper.find("Dialog")
    expect(removeDialog.prop("open")).toBe(true)
    removeDialog.prop("onAccept")()
    wrapper.update()
    expect(wrapper.find("Nestable").prop("items")).toEqual(
      dummyInternalMenuItems.slice(1)
    )
  })

  it("should put an appropriate title on the modal", () => {
    ["edit", "add"].forEach(action => {
      const menuItem = action === "edit" ? dummyInternalMenuItems[0] : null
      const wrapper = render()
      expect(wrapper.find("BasicModal").prop("isVisible")).toBe(false)
      const nestable = wrapper.find("Nestable")
      let formShowBtn
      if (menuItem) {
        const renderedMenuItem = shallow(
          nestable.prop("renderItem")({ item: menuItem })
        )
        formShowBtn = renderedMenuItem.find("button").at(0)
      } else {
        formShowBtn = wrapper.find("button.cyan-button")
      }
      const preventDefaultStub = jest.fn()
      formShowBtn.prop("onClick")({ preventDefault: preventDefaultStub })
      wrapper.update()
      const modal = wrapper.find("BasicModal")
      expect(modal.prop("isVisible")).toBe(true)
      expect(modal.prop("title")).toBe(
        action === "edit" ? "Edit Navigation Item" : "Add Navigation Item"
      )
    })
  })

  it("should show a form to edit existing menu items", () => {
    const menuItem = dummyInternalMenuItems[0]
    const menuItemForm = renderMenuItemForm(menuItem)
    const formProps = menuItemForm.props()
    expect(formProps.activeItem).toEqual(menuItem)
    expect(formProps.existingMenuIds).toEqual(
      new Set([
        "external-12345",
        "32629a02-3dc5-4128-8e43-0392b51e7b61",
        "32629a02-3dc5-4128-8e43-0392b51e7b62",
        "32629a02-3dc5-4128-8e43-0392b51e7b63"
      ])
    )
  })
  ;[
    [false, false, "new menu item, external link"],
    [false, true, "new menu item, internal link"],
    [true, false, "existing menu item, external link"],
    [true, true, "existing menu item, internal link"]
  ].forEach(([useExistingItem, isInternalLink, desc]) => {
    it(`menu item form should correctly update widget value with ${desc}`, async () => {
      let submitData, expPartialIdentifier, expectedMenuItem
      const initialMenuItemCount = dummyHugoItems.length
      const title = "My Title"
      const internalLinkUuid = "12629a02-3dc5-4128-8e43-0392b51e7b61"
      const externalLinkUrl = "http://example.com"
      const menuItem = useExistingItem ?
        dummyInternalMenuItems[0].children[0] :
        null
      const menuItemForm = renderMenuItemForm(menuItem)
      const formProps = menuItemForm.props()
      if (isInternalLink) {
        submitData = {
          menuItemTitle: title,
          menuItemType:  LinkType.Internal,
          internalLink:  internalLinkUuid
        }
        expectedMenuItem = {
          name: title
        }
        expPartialIdentifier = internalLinkUuid
      } else {
        submitData = {
          menuItemTitle: title,
          menuItemType:  LinkType.External,
          externalLink:  externalLinkUrl
        }
        expectedMenuItem = {
          name: title,
          url:  externalLinkUrl
        }
        expPartialIdentifier = `${EXTERNAL_LINK_PREFIX}-631280213`
      }
      formProps.onSubmit(submitData)
      expect(onChangeStub.mock.calls.length).toEqual(1)
      const matchingMenuItem = useExistingItem ?
        {
          ...expectedMenuItem,
          weight: 10,
          parent: "32629a02-3dc5-4128-8e43-0392b51e7b61"
        } :
        {
          ...expectedMenuItem,
          weight: 30
        }
      const updatedHugoMenuItems = onChangeStub.mock.calls[0][0].target.value
      const updatedHugoMenuItem = updatedHugoMenuItems.find(
        (item: HugoItem) => item.name === matchingMenuItem.name
      )
      expect(updatedHugoMenuItem).toEqual(
        expect.objectContaining(matchingMenuItem)
      )
      expect(updatedHugoMenuItem.identifier).toEqual(
        expect.stringContaining(expPartialIdentifier)
      )
      expect(updatedHugoMenuItems).toHaveLength(
        useExistingItem ? initialMenuItemCount : initialMenuItemCount + 1
      )
    })
  })
})
