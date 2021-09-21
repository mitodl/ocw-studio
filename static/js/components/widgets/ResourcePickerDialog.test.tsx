import React from "react"
import { act } from "react-dom/test-utils"
import { TabPane } from "reactstrap"
import Switch from "react-switch"
import { ReactWrapper } from "enzyme"

import ResourcePickerDialog from "./ResourcePickerDialog"
import IntegrationTestHelper, {
  TestRenderer
} from "../../util/integration_test_helper"
import { useDebouncedState } from "../../hooks/state"
import { useState } from "react"
import { makeWebsiteContentDetail } from "../../util/factories/websites"
import { WebsiteContent } from "../../types/websites"
import {
  RESOURCE_EMBED,
  RESOURCE_LINK
} from "../../lib/ckeditor/plugins/constants"
import {
  RESOURCE_TYPE_IMAGE,
  RESOURCE_TYPE_DOCUMENT,
  RESOURCE_TYPE_VIDEO
} from "../../constants"

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
    wrapper.find("ResourcePickerListing").prop("focusResource")(
      resource.text_id
    )
  })
  wrapper.update()
}

describe("ResourcePickerDialog", () => {
  let helper: IntegrationTestHelper,
    render: TestRenderer,
    insertEmbedStub: any,
    setOpenStub: any,
    setStub: any,
    resource: WebsiteContent

  beforeEach(() => {
    helper = new IntegrationTestHelper()

    insertEmbedStub = helper.sandbox.stub()
    setOpenStub = helper.sandbox.stub()
    resource = makeWebsiteContentDetail()

    setStub = helper.sandbox.stub()
    // @ts-ignore
    useDebouncedState.mockReturnValue(["", setStub])

    render = helper.configureRenderer(ResourcePickerDialog, {
      open:        true,
      setOpen:     setOpenStub,
      insertEmbed: insertEmbedStub,
      attach:      "resource"
    })
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("should render tabs", async () => {
    const { wrapper } = await render()
    expect(wrapper.find(TabPane).map(pane => pane.prop("tabId"))).toEqual([
      RESOURCE_TYPE_IMAGE,
      RESOURCE_TYPE_VIDEO,
      RESOURCE_TYPE_DOCUMENT
    ])
  })

  it("should pass some basic props down to the dialog", async () => {
    const { wrapper } = await render()
    const dialog = wrapper.find("Dialog")
    expect(dialog.prop("open")).toBeTruthy()
    expect(dialog.prop("wrapClassName")).toBe("resource-picker-dialog")
  })

  it("should allow focusing and linking a resource", async () => {
    const { wrapper } = await render()
    // callback should be 'undefined' before resource is focused
    expect(wrapper.find("Dialog").prop("altOnAccept")).toBeUndefined()
    focusResource(wrapper, resource)

    act(() => {
      // @ts-ignore
      wrapper.find("Dialog").prop("altOnAccept")()
    })

    wrapper.update()

    expect(insertEmbedStub.args[0]).toStrictEqual([
      resource.text_id,
      RESOURCE_LINK
    ])
  })

  it("should focusing and embedding a resource", async () => {
    const { wrapper } = await render()
    // callback should be 'undefined' before resource is focused
    expect(wrapper.find("Dialog").prop("onAccept")).toBeUndefined()
    focusResource(wrapper, resource)

    act(() => {
      // @ts-ignore
      wrapper.find("Dialog").prop("onAccept")()
    })

    wrapper.update()

    expect(insertEmbedStub.args[0]).toStrictEqual([
      resource.text_id,
      RESOURCE_EMBED
    ])
  })

  it("should pass basic props to ResourcePickerListing", async () => {
    const { wrapper } = await render()
    expect(wrapper.find("ResourcePickerListing").prop("attach")).toEqual(
      "resource"
    )
    focusResource(wrapper, resource)
    expect(wrapper.find("ResourcePickerListing").prop("focusedResource")).toBe(
      resource.text_id
    )
  })

  it("should pass correct resourcetype to active tab", async () => {
    const { wrapper } = await render()

    //
    ;[RESOURCE_TYPE_IMAGE, RESOURCE_TYPE_VIDEO, RESOURCE_TYPE_DOCUMENT].forEach(
      (resourcetype, idx) => {
        act(() => {
          wrapper
            .find("NavLink")
            .at(idx)
            .simulate("click")
        })
        wrapper.update()
        expect(
          wrapper.find("ResourcePickerListing").prop("resourcetype")
        ).toEqual(resourcetype)
      }
    )
  })

  it("should pass filter string to picker, when filter is on", async () => {
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

    wrapper
      .find(Switch)
      .find(".react-switch-bg")
      .simulate("click")
    wrapper.update()
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
