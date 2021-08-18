import React from "react"
import { act } from "react-dom/test-utils"
import { TabPane } from "reactstrap"
import Switch from "react-switch"

import ResourcePickerDialog from "./ResourcePickerDialog"
import IntegrationTestHelper, {
  TestRenderer
} from "../../util/integration_test_helper"
import { useDebouncedState } from "../../hooks/state"
import { useState } from "react"

jest.mock("../../hooks/state")

function ResourcePickerListing() {
  return <div>mock</div>
}

// mock this, otherwise it makes requests and whatnot
jest.mock("./ResourcePickerListing", () => ({
  __esModule: true,
  default:    ResourcePickerListing
}))

describe("ResourcePickerDialog", () => {
  let helper: IntegrationTestHelper,
    render: TestRenderer,
    insertEmbedStub: any,
    setOpenStub: any,
    setStub: any

  beforeEach(() => {
    helper = new IntegrationTestHelper()

    insertEmbedStub = helper.sandbox.stub()
    setOpenStub = helper.sandbox.stub()

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
      "Image",
      "Video",
      "Document"
    ])
  })

  it("should pass some props down to the dialog", async () => {
    const { wrapper } = await render()
    const dialog = wrapper.find("Dialog")
    expect(dialog.prop("open")).toBeTruthy()
    expect(dialog.prop("wrapClassName")).toBe("resource-picker-dialog")
  })

  it("should pass basic props to ResourcePickerListing", async () => {
    const { wrapper } = await render()
    expect(wrapper.find("ResourcePickerListing").prop("insertEmbed")).toEqual(
      insertEmbedStub
    )
    expect(wrapper.find("ResourcePickerListing").prop("setOpen")).toEqual(
      setOpenStub
    )
    expect(wrapper.find("ResourcePickerListing").prop("attach")).toEqual(
      "resource"
    )
  })

  it("should pass correct filetype to active tab", async () => {
    const { wrapper } = await render()

    //
    ;["Image", "Video", "Document"].forEach((filetype, idx) => {
      act(() => {
        wrapper
          .find("NavLink")
          .at(idx)
          .simulate("click")
      })
      wrapper.update()
      expect(wrapper.find("ResourcePickerListing").prop("filetype")).toEqual(
        filetype
      )
    })
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
