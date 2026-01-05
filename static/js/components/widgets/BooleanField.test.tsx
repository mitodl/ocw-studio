import React from "react"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import BooleanField from "./BooleanField"

describe("BooleanField", () => {
  let renderComponent: any, onChangeStub: any

  beforeEach(() => {
    onChangeStub = jest.fn()

    renderComponent = (props = {}) =>
      render(
        <BooleanField
          name="name"
          value={false}
          onChange={onChangeStub}
          {...props}
        />,
      )
  })

  it("should render two radio inputs", () => {
    renderComponent()
    const inputs = screen.getAllByRole("radio")
    expect(inputs).toHaveLength(2)
    inputs.forEach((input) => {
      expect(input).toHaveAttribute("name", "name")
      expect(input).toHaveAttribute("type", "radio")
      const value = input.getAttribute("value")
      expect(input).toHaveAttribute(
        "id",
        value === "true" ? "name_true" : "name_false",
      )
    })
  })

  it("should set 'checked' prop on the radio corresponding to current value", () => {
    ;[true, false].forEach((value) => {
      const { unmount } = renderComponent({ value })
      const checkedRadio = screen.getByRole("radio", {
        name: value ? "True" : "False",
      })
      const uncheckedRadio = screen.getByRole("radio", {
        name: value ? "False" : "True",
      })

      expect(checkedRadio).toBeChecked()
      expect(uncheckedRadio).not.toBeChecked()
      unmount()
    })
  })

  it("clicking on a radio option should call setFieldValue", async () => {
    const user = userEvent.setup()

    const { unmount } = renderComponent({ value: false })
    const yesRadio = screen.getByRole("radio", { name: "True" })
    await user.click(yesRadio)
    expect(onChangeStub).toHaveBeenCalledWith({
      target: { name: "name", value: true },
    })

    unmount()
    onChangeStub.mockClear()

    renderComponent({ value: true })
    const noRadio = screen.getByRole("radio", { name: "False" })
    await user.click(noRadio)
    expect(onChangeStub).toHaveBeenCalledWith({
      target: { name: "name", value: false },
    })
  })
})
