import React from "react"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import sinon, { SinonStub } from "sinon"

import Dialog from "./Dialog"

describe("Dialog", () => {
  let onCancelStub: SinonStub, onAcceptStub: SinonStub

  beforeEach(() => {
    onCancelStub = sinon.stub()
    onAcceptStub = sinon.stub()
  })

  afterEach(() => {
    sinon.restore()
  })

  it("renders a Dialog with expected content, functional buttons, and default button text", async () => {
    const user = userEvent.setup()
    const { unmount } = render(
      <Dialog
        onAccept={onAcceptStub}
        onCancel={onCancelStub}
        open={true}
        headerContent="Header"
        bodyContent={<div>Body</div>}
      />,
    )

    expect(screen.getByRole("dialog")).toBeInTheDocument()
    expect(screen.getByText("Body")).toBeInTheDocument()
    expect(screen.getByText("Header")).toBeInTheDocument()

    const cancelButton = screen.getByRole("button", { name: "Cancel" })
    await user.click(cancelButton)
    sinon.assert.calledOnce(onCancelStub)

    const okButton = screen.getByRole("button", { name: "OK" })
    await user.click(okButton)
    sinon.assert.calledOnce(onAcceptStub)

    unmount()
  })

  it("renders a Dialog with passed button text", () => {
    const { unmount } = render(
      <Dialog
        onAccept={onAcceptStub}
        onCancel={onCancelStub}
        open={true}
        headerContent={<span>Header</span>}
        bodyContent={<div>Body</div>}
        acceptText="Save"
        cancelText="Back"
      />,
    )

    expect(screen.getByRole("button", { name: "Back" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Save" })).toBeInTheDocument()

    unmount()
  })

  it("does not render when open is false", () => {
    const { unmount } = render(
      <Dialog
        onAccept={onAcceptStub}
        onCancel={onCancelStub}
        open={false}
        headerContent="Header"
        bodyContent={<div>Body</div>}
      />,
    )

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()

    unmount()
  })

  it("sets various classnames", () => {
    const { unmount } = render(
      <Dialog
        onAccept={onAcceptStub}
        onCancel={onCancelStub}
        open={true}
        headerContent="Header"
        bodyContent={<div>Body</div>}
        wrapClassName="wrap"
        modalClassName="modal"
        backdropClassName="backdrop"
        contentClassName="content"
      />,
    )

    expect(screen.getByRole("dialog")).toHaveClass("modal")

    unmount()
  })
})
