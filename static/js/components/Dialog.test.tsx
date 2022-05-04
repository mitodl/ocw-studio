import React from "react"
import { shallow, ShallowWrapper } from "enzyme"
import sinon, { SinonStub } from "sinon"

import Dialog from "./Dialog"

interface ExtraProps {
  open: boolean
  acceptText?: string
  altAcceptText?: string
  cancelText?: string
  headerContent: JSX.Element | string
  bodyContent: JSX.Element | string
  wrapClassName?: string
  modalClassName?: string
  backdropClassName?: string
  contentClassName?: string
}

describe("Dialog", () => {
  let toggleModalStub: SinonStub,
    onCancelStub: SinonStub,
    onAcceptStub: SinonStub,
    headerContent: JSX.Element | string,
    bodyContent: JSX.Element | string,
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
      .at(2)
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
      altAcceptText,
      cancelText
    })
    expect(wrapper.find("Modal").prop("isOpen")).toBe(false)
    const okButton = wrapper
      .find("ModalFooter")
      .find("Button")
      .at(0)
    expect(okButton.childAt(0).text()).toBe(acceptText)

    expect(
      wrapper
        .find("ModalFooter")
        .find("Button")
        .at(1)
        .childAt(0)
        .text()
    ).toBe(altAcceptText)

    const cancelButton = wrapper
      .find("ModalFooter")
      .find("Button")
      .at(2)
    expect(cancelButton.childAt(0).text()).toBe(cancelText)
  })

  it("sets various classnames", () => {
    headerContent = "Header"
    bodyContent = <div>Body</div>
    const wrapper = render({
      headerContent,
      bodyContent,
      open:              true,
      wrapClassName:     "wrap",
      modalClassName:    "modal",
      backdropClassName: "backdrop",
      contentClassName:  "content"
    })
    expect(wrapper.find("Modal").prop("wrapClassName")).toBe("wrap")
    expect(wrapper.find("Modal").prop("modalClassName")).toBe("modal")
    expect(wrapper.find("Modal").prop("backdropClassName")).toBe("backdrop")
    expect(wrapper.find("Modal").prop("contentClassName")).toBe("content")
  })
})
