import React from "react"
import { shallow } from "enzyme"

import BooleanField from "./BooleanField"

describe("BooleanField", () => {
  let render: any, onChangeStub: any

  beforeEach(() => {
    onChangeStub = jest.fn()

    render = (props = {}) =>
      shallow(
        <BooleanField
          name="name"
          value={false}
          onChange={onChangeStub}
          {...props}
        />,
      )
  })

  it("should render two radio inputs", () => {
    const wrapper = render()
    wrapper.find("input").map((input: any) => {
      const { name, type, id, value } = input.props()
      expect(name).toBe("name")
      expect(type).toBe("radio")
      expect(id).toBe(value === "true" ? "name_true" : "name_false")
    })
  })

  it("should set 'checked' prop on the radio corresponding to current value", () => {
    ;[true, false].forEach((value) => {
      const wrapper = render({ value })
      expect(
        wrapper.find(`#name_${value.toString()}`).prop("checked"),
      ).toBeTruthy()
      expect(
        wrapper.find(`#name_${(!value).toString()}`).prop("checked"),
      ).toBeFalsy()
    })
  })

  it("clicking on a radio option should call setFieldValue", () => {
    const wrapper = render()
    const name = "name"
    wrapper
      .find("input")
      .at(0)
      .simulate("change", { target: { name, value: "true" } })
    expect(onChangeStub).toHaveBeenCalledWith({
      target: { name: "name", value: true },
    })
    wrapper
      .find("input")
      .at(1)
      .simulate("change", { target: { name, value: "false" } })
    expect(onChangeStub).toHaveBeenCalledWith({
      target: { name: "name", value: false },
    })
  })

  it("passing additional_labels should change radio labels", () => {
    const wrapper = render({
      name: "name",
      additional_labels: {
        true_label: "custom true",
        false_label: "custom false",
      },
    })

    const trueLabel = wrapper.find('label[htmlFor="name_true"]')
    const falseLabel = wrapper.find('label[htmlFor="name_false"]')

    expect(trueLabel.text()).toBe("custom true")
    expect(falseLabel.text()).toBe("custom false")
  })

  it("should have default labels", () => {
    const wrapper = render({
      name: "name",
    })

    const trueLabel = wrapper.find('label[htmlFor="name_true"]')
    const falseLabel = wrapper.find('label[htmlFor="name_false"]')

    expect(trueLabel.text()).toBe("True")
    expect(falseLabel.text()).toBe("False")
  })
})
