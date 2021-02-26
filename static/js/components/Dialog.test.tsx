import React, { Component } from "react"
import { shallow, ShallowWrapper } from "enzyme"
import sinon, { SinonStub } from "sinon"

import Dialog from "./Dialog"

interface ExtraProps {
  open: boolean
  acceptText?: string
  cancelText?: string
  headerContent: JSX.Element | string
  bodyContent: JSX.Element | string
}

describe("Dialog", () => {
  let toggleModalStub: SinonStub,
    onCancelStub: SinonStub,
    onAcceptStub: SinonStub,
    headerContent: Component | JSX.Element | string,
    bodyContent: Component | JSX.Element | string,
    render: (props: ExtraProps) => ShallowWrapper

  beforeEach(() => {
    toggleModalStub = sinon.stub()
    onCancelStub = sinon.stub()
    onAcceptStub = sinon.stub()
    render = (props: ExtraProps) =>
      shallow(
        <Dialog
          toggleModal={toggleModalStub}
          onAccept={onAcceptStub}
          onCancel={onCancelStub}
          {...props}
        />
      )
  })

  it("renders a Dialog with expected content, functional buttons and default button text", () => {
    headerContent = "Header"
    bodyContent = <div>Body</div>
    const wrapper = render({ open: true, headerContent, bodyContent })
    expect(wrapper.find("Modal").prop("isOpen")).toBe(true)
    expect(wrapper.find("Modal").prop("toggle")).toBe(toggleModalStub)
    expect(
      wrapper
        .find("ModalBody")
        .childAt(0)
        .text()
    ).toBe("Body")
    expect(
      wrapper
        .find("ModalHeader")
        .childAt(0)
        .text()
    ).toBe(headerContent)

    const okButton = wrapper
      .find("ModalFooter")
      .find("Button")
      .at(0)
    expect(okButton.childAt(0).text()).toBe("OK")
    okButton.simulate("click")
    sinon.assert.calledOnce(onAcceptStub)

    const cancelButton = wrapper
      .find("ModalFooter")
      .find("Button")
      .at(1)
    expect(cancelButton.childAt(0).text()).toBe("Cancel")
    cancelButton.simulate("click")
    sinon.assert.calledOnce(onCancelStub)
  })

  it("renders a Dialog with passed button text", () => {
    headerContent = <h1>Header</h1>
    bodyContent = <div>Body</div>
    const acceptText = "Save"
    const cancelText = "Back"
    const wrapper = render({
      open: false,
      headerContent,
      bodyContent,
      acceptText,
      cancelText
    })
    expect(wrapper.find("Modal").prop("isOpen")).toBe(false)
    const okButton = wrapper
      .find("ModalFooter")
      .find("Button")
      .at(0)
    expect(okButton.childAt(0).text()).toBe(acceptText)

    const cancelButton = wrapper
      .find("ModalFooter")
      .find("Button")
      .at(1)
    expect(cancelButton.childAt(0).text()).toBe(cancelText)
  })
})
