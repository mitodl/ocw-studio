import React from "react"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import sinon, { SinonStub } from "sinon"

import BasicModal from "./BasicModal"

describe("BasicModal", () => {
  const className = "my-class",
    title = "My Title",
    dummyJsx = <div>...</div>
  let hideModalStub: SinonStub, childFunctionStub: SinonStub

  beforeEach(() => {
    hideModalStub = sinon.stub()
    childFunctionStub = sinon.stub().returns(dummyJsx)
  })

  afterEach(() => {
    sinon.restore()
  })

  it("renders a modal with a title and the correct props", () => {
    const { unmount } = render(
      <BasicModal
        isVisible={true}
        hideModal={hideModalStub}
        className={className}
        title={title}
      >
        {childFunctionStub}
      </BasicModal>,
    )
    expect(screen.getByRole("dialog")).toBeInTheDocument()
    expect(screen.getByRole("dialog")).toHaveClass(className)
    expect(screen.getByText(title)).toBeInTheDocument()
    expect(screen.getByText("...")).toBeInTheDocument()
    sinon.assert.calledOnceWithExactly(childFunctionStub, {
      hideModal: hideModalStub,
    })
    unmount()
  })

  it("calls hideModal when close button is clicked", async () => {
    const user = userEvent.setup()
    const { unmount } = render(
      <BasicModal
        isVisible={true}
        hideModal={hideModalStub}
        className={className}
        title={title}
      >
        {childFunctionStub}
      </BasicModal>,
    )
    const closeButton = screen.getByLabelText(/close/i)
    await user.click(closeButton)
    sinon.assert.called(hideModalStub)
    unmount()
  })
})
