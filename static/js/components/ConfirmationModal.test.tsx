import React from "react"
import { shallow } from "enzyme"
import { useBeforeunload } from "react-beforeunload"

import ConfirmationModal from "./ConfirmationModal"

jest.mock("react-beforeunload", () => ({
  __esModule:      true,
  useBeforeunload: jest.fn()
}))

describe("ConfirmationModal", () => {
  let dirty: boolean,
    confirmationModalVisible: boolean,
    setConfirmationModalVisible: any,
    dismiss: any

  beforeEach(() => {
    dismiss = jest.fn()
    setConfirmationModalVisible = jest.fn()
    confirmationModalVisible = false
    // @ts-ignore
    useBeforeunload.mockClear()
  })

  const render = (props = {}) =>
    shallow(
      <ConfirmationModal
        dirty={dirty}
        confirmationModalVisible={confirmationModalVisible}
        setConfirmationModalVisible={setConfirmationModalVisible}
        dismiss={dismiss}
        {...props}
      />
    )

  it("renders a modal", () => {
    const wrapper = render()
    const modal = wrapper.find("BasicModal")
    expect(modal.prop("title")).toBe("Discard changes")
    // @ts-ignore
    const children = shallow(modal.prop("children")())
    expect(children.text()).toContain(
      "You have unsaved changes. Are you sure you want to discard your changes?"
    )
  })

  it("hides the modal via the cancel button", () => {
    const wrapper = render()
    const modal = wrapper.find("BasicModal")
    // @ts-ignore
    const children = shallow(modal.prop("children")())
    const cancelButton = children.find(".cancel")
    // @ts-ignore
    cancelButton.prop("onClick")()
    expect(setConfirmationModalVisible).toBeCalledWith(false)
  })

  it("dismisses via the discard button", () => {
    const wrapper = render()
    const modal = wrapper.find("BasicModal")
    // @ts-ignore
    const children = shallow(modal.prop("children")())
    const discardButton = children.find(".discard")
    // @ts-ignore
    discardButton.prop("onClick")()
    expect(dismiss).toBeCalledWith()
  })

  //
  ;[true, false].forEach(visible => {
    it(`${visible ? "is" : "is not"} visible`, () => {
      const wrapper = render({ confirmationModalVisible: visible })
      const modal = wrapper.find("BasicModal")
      expect(modal.prop("isVisible")).toBe(visible)
    })
  })

  it("hides the confirmation modal", () => {
    const wrapper = render()
    // @ts-ignore
    wrapper.find("BasicModal").prop("hideModal")()
    expect(setConfirmationModalVisible).toBeCalledWith(false)
  })

  //
  ;[
    [
      true,
      "You have unsaved changes. Are you sure you want to leave this page?"
    ],
    [false, null]
  ].forEach(([dirty, expectedMessage]) => {
    it(`sets a beforeunload handler when dirty=${String(dirty)}`, async () => {
      render({ dirty })
      expect(useBeforeunload).toBeCalled()
      // @ts-ignore
      const message = useBeforeunload.mock.calls[0][0]()
      expect(message).toBe(expectedMessage)
    })
  })
})
