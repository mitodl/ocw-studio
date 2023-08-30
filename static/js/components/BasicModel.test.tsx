import React from "react"
import { shallow, ShallowWrapper } from "enzyme"
import sinon, { SinonStub } from "sinon"

import BasicModal from "./BasicModal"

interface ExtraProps {
  hideModal?: () => void
}
type ChildrenProp = (props: any) => JSX.Element | null

describe("BasicModal", () => {
  const className = "my-class",
    title = "My Title",
    dummyJsx = <div>...</div>
  let render: (props?: ExtraProps) => ShallowWrapper,
    hideModalStub: SinonStub,
    childFunctionStub: SinonStub

  beforeEach(() => {
    hideModalStub = sinon.stub()
    childFunctionStub = sinon.stub().returns(dummyJsx)
    render = (props?: ExtraProps, children?: ChildrenProp) =>
      shallow(
        <BasicModal
          isVisible={true}
          hideModal={hideModalStub}
          className={className}
          title={title}
          {...props}
        >
          {children ?? childFunctionStub}
        </BasicModal>,
      )
  })

  it("renders a modal with a title and the correct props", () => {
    const wrapper = render()
    const modal = wrapper.find("Modal")
    expect(modal.exists()).toBe(true)
    expect(modal.props()).toEqual(
      expect.objectContaining({
        isOpen: true,
        toggle: hideModalStub,
        modalClassName: className,
      }),
    )
    const header = modal.find("ModalHeader")
    expect(header.props()).toEqual(
      expect.objectContaining({
        toggle: hideModalStub,
        children: title,
      }),
    )
    sinon.assert.calledOnceWithExactly(childFunctionStub, {
      hideModal: hideModalStub,
    })
    expect(modal.find("ModalBody").prop("children")).toEqual(dummyJsx)
  })
})
