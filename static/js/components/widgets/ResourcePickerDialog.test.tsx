import React from "react"
import { act } from "react-dom/test-utils"
import { TabPane, NavLink, Dropdown, DropdownItem } from "reactstrap"
import { ReactWrapper } from "enzyme"

import ResourcePickerDialog, { TabIds } from "./ResourcePickerDialog"
import IntegrationTestHelper, {
  TestRenderer
} from "../../util/integration_test_helper"
import { useDebouncedState } from "../../hooks/state"
import { useState } from "react"
import {
  makeWebsiteContentDetail,
  makeWebsiteDetail
} from "../../util/factories/websites"
import { WebsiteContent } from "../../types/websites"
import {
  RESOURCE_EMBED,
  RESOURCE_LINK
} from "../../lib/ckeditor/plugins/constants"
import { ResourceType } from "../../constants"

jest.mock("../../hooks/state")

function ResourcePickerListing() {
  return <div>mock</div>
}

// mock this, otherwise it makes requests and whatnot
jest.mock("./ResourcePickerListing", () => ({
  __esModule: true,
  default:    ResourcePickerListing
}))

const focusResource = (wrapper: ReactWrapper, resource: WebsiteContent) => {
  act(() => {
    // @ts-ignore
    wrapper.find("ResourcePickerListing").prop("focusResource")(resource)
  })
  wrapper.update()
}

describe("ResourcePickerDialog", () => {
  let helper: IntegrationTestHelper,
    render: TestRenderer,
    insertEmbedStub: sinon.SinonStub,
    closeDialogStub: sinon.SinonStub,
    setStub: sinon.SinonStub,
    resource: WebsiteContent,
    collectionsWebsite: string

  beforeEach(() => {
    helper = new IntegrationTestHelper()

    insertEmbedStub = helper.sandbox.stub()
    closeDialogStub = helper.sandbox.stub()
    resource = makeWebsiteContentDetail()
    collectionsWebsite = makeWebsiteDetail().name

    setStub = helper.sandbox.stub()
    // @ts-ignore
    useDebouncedState.mockReturnValue(["", setStub])

    render = helper.configureRenderer(ResourcePickerDialog, {
      mode:        RESOURCE_EMBED,
      isOpen:      true,
      closeDialog: closeDialogStub,
      insertEmbed: insertEmbedStub,
      collectionsWebsite
    })
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("should render 3 tabs when embedding", async () => {
    const { wrapper } = await render({ mode: RESOURCE_EMBED })
    expect(wrapper.find(TabPane).map(pane => pane.prop("tabId"))).toEqual([
      TabIds.Documents,
      TabIds.Videos,
      TabIds.Images
    ])
  })

  it("should render 6 tabs when linking", async () => {
    const { wrapper } = await render({ mode: RESOURCE_LINK })
    expect(wrapper.find(TabPane).map(pane => pane.prop("tabId"))).toEqual([
      TabIds.Documents,
      TabIds.Videos,
      TabIds.Images,
      TabIds.Pages,
      TabIds.CourseCollections,
      TabIds.ResourceCollections
    ])
  })

  test("TabIds values are unique", () => {
    const uniqueTabIds = new Set(Object.values(TabIds))
    expect(Object.values(TabIds).length).toBe(uniqueTabIds.size)
  })

  it.each([
    { mode: RESOURCE_LINK, dropdownExists: true, should: "should" },
    { mode: RESOURCE_EMBED, dropdownExists: false, should: "should not" }
  ])(
    'when in mode "$mode", $should show the "more" dropdown',
    async ({ mode, dropdownExists }) => {
      const { wrapper } = await render({ mode })
      const dropdown = wrapper.find(Dropdown)
      expect(dropdown.exists()).toBe(dropdownExists)
    }
  )

  it("should pass some basic props down to the dialog", async () => {
    const { wrapper } = await render()
    const dialog = wrapper.find("Dialog")
    expect(dialog.prop("open")).toBeTruthy()
    expect(dialog.prop("wrapClassName")).toBe("resource-picker-dialog")
  })

  it("should allow focusing and linking a resource, then close the dialog", async () => {
    const { wrapper } = await render({
      mode: RESOURCE_LINK
    })
    // callback should be 'undefined' before resource is focused
    expect(wrapper.find("Dialog").prop("onAccept")).toBeUndefined()
    focusResource(wrapper, resource)

    expect(wrapper.find("Dialog").prop("acceptText")).toBe("Add link")

    act(() => {
      // @ts-ignore
      wrapper.find("Dialog").prop("onAccept")()
    })

    wrapper.update()

    expect(insertEmbedStub.args[0]).toStrictEqual([
      resource.text_id,
      resource.title,
      RESOURCE_LINK
    ])
    expect(closeDialogStub.callCount).toBe(1)
  })

  it("should focusing and embedding a resource", async () => {
    const { wrapper } = await render({
      mode: RESOURCE_EMBED
    })
    // callback should be 'undefined' before resource is focused
    expect(wrapper.find("Dialog").prop("onAccept")).toBeUndefined()
    focusResource(wrapper, resource)

    expect(wrapper.find("Dialog").prop("acceptText")).toBe("Embed resource")

    act(() => {
      // @ts-ignore
      wrapper.find("Dialog").prop("onAccept")()
    })

    wrapper.update()

    expect(insertEmbedStub.args[0]).toStrictEqual([
      resource.text_id,
      resource.title,
      RESOURCE_EMBED
    ])
  })

  it("should pass basic props to ResourcePickerListing", async () => {
    const { wrapper } = await render()
    expect(wrapper.find("ResourcePickerListing").prop("contentType")).toEqual(
      "resource"
    )
    focusResource(wrapper, resource)
    expect(wrapper.find("ResourcePickerListing").prop("focusedResource")).toBe(
      resource
    )
  })

  it.each([
    {
      index:        0,
      resourcetype: ResourceType.Document,
      contentType:  "resource",
      singleColumn: true
    },
    {
      index:        1,
      resourcetype: ResourceType.Video,
      contentType:  "resource",
      singleColumn: false
    },
    {
      index:        2,
      resourcetype: ResourceType.Image,
      contentType:  "resource",
      singleColumn: false
    },
    { index: 3, resourcetype: null, contentType: "page", singleColumn: true }
  ])(
    "passes the correct props to ResourcePickerListing when main tab $index is clicked",
    async ({ resourcetype, contentType, singleColumn, index }) => {
      const { wrapper } = await render({ mode: RESOURCE_LINK })
      act(() => {
        wrapper
          .find(NavLink)
          .at(index)
          .simulate("click")
      })
      wrapper.update()
      const listing = wrapper.find(ResourcePickerListing)
      expect(listing.prop("resourcetype")).toEqual(resourcetype)
      expect(listing.prop("contentType")).toBe(contentType)
      expect(listing.prop("singleColumn")).toBe(singleColumn)
    }
  )

  it.each([
    {
      index:        0,
      resourcetype: null,
      contentType:  "course_collections"
    },
    {
      index:        1,
      resourcetype: null,
      contentType:  "resource_collections"
    }
  ])(
    "passes the correct resourcetype and contentType when dropdown tab $index is clicked",
    async ({ resourcetype, contentType, index }) => {
      const { wrapper } = await render({ mode: RESOURCE_LINK })
      act(() => {
        wrapper
          .find(DropdownItem)
          .at(index)
          .simulate("click")
      })
      wrapper.update()
      const listing = wrapper.find(ResourcePickerListing)
      expect(listing.prop("resourcetype")).toEqual(resourcetype)
      expect(listing.prop("contentType")).toBe(contentType)
      expect(listing.prop("sourceWebsiteName")).toBe(collectionsWebsite)
    }
  )

  it("should pass filter string to picker, when filter is set", async () => {
    const setStub = helper.sandbox.stub()
    // @ts-ignore
    useDebouncedState.mockImplementation((initial, _ms) => {
      // this is just to un-debounce to make testing easier
      const [state, setState] = useState(initial)

      return [
        state,
        (update: any) => {
          setStub(update)
          setState(update)
        }
      ]
    })

    const { wrapper } = await render()

    act(() => {
      wrapper.find("input.filter-input").prop("onChange")!({
        // @ts-ignore
        currentTarget: { value: "new filter" }
      })
    })
    wrapper.update()

    expect(wrapper.find("ResourcePickerListing").prop("filter")).toEqual(
      "new filter"
    )
  })
})
