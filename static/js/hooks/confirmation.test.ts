import { renderHook, act } from "@testing-library/react-hooks"

import useConfirmation from "./confirmation"

describe("confirmation hook", () => {
  let dirty: boolean, setDirtyStub: any, closeStub: any

  beforeEach(() => {
    dirty = false
    setDirtyStub = jest.fn()
    closeStub = jest.fn()
  })

  const renderConfirmationHook = (props = {}) =>
    renderHook(() =>
      useConfirmation({
        dirty,
        setDirty: setDirtyStub,
        close:    closeStub,
        ...props
      })
    )

  it("exposes a setter for confirmation modal visibility", async () => {
    const { result, rerender } = renderConfirmationHook()
    act(() => result.current.setConfirmationModalVisible(false))
    rerender()
    expect(result.current.confirmationModalVisible).toBeFalsy()
    act(() => result.current.setConfirmationModalVisible(true))
    rerender()
    expect(result.current.confirmationModalVisible).toBeTruthy()
  })
  ;[
    [true, true, false],
    [true, false, true],
    [false, true, false],
    [false, false, false]
  ].forEach(([dirty, skipConfirmation, expectVisible]) => {
    it(`${
      expectVisible ? "shows" : "doesn't show"
    } the confirmation modal when dirty=${String(
      dirty
    )} and skipConfirmation=${String(skipConfirmation)}`, () => {
      const { result, rerender } = renderConfirmationHook({ dirty })
      const { conditionalClose } = result.current
      act(() => conditionalClose(skipConfirmation))
      rerender()
      expect(result.current.confirmationModalVisible).toBe(expectVisible)
      if (!expectVisible) {
        expect(setDirtyStub).toBeCalledWith(false)
        expect(closeStub).toBeCalledWith()
      }
    })
  })
})
