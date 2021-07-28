import React from "react"
import sinon, { SinonSandbox, SinonStub } from "sinon"
import { mount } from "enzyme"
import Select from "react-select"
import AsyncSelect from "react-select/async"

import SelectField, { Option } from "./SelectField"

describe("SelectField", () => {
  let sandbox: SinonSandbox,
    onChangeStub: SinonStub,
    name: string,
    options: Array<string | Option>,
    expectedOptions: Option[],
    min: number,
    max: number

  beforeEach(() => {
    sandbox = sinon.createSandbox()
    onChangeStub = sandbox.stub()
    options = ["one", "two", { label: "Three", value: "3" }]
    expectedOptions = [
      { label: "one", value: "one" },
      { label: "two", value: "two" },
      { label: "Three", value: "3" }
    ]
    min = 1
    max = 3
  })

  afterEach(() => {
    sandbox.restore()
  })

  const render = (props: any) =>
    mount(
      <SelectField
        onChange={onChangeStub}
        name={name}
        min={min}
        max={max}
        options={options}
        {...props}
      />
    )

  it("should pass placeholder to Select", () => {
    const wrapper = render({
      placeholder: "This place is held!"
    })
    expect(wrapper.find("Select").prop("placeholder")).toBe(
      "This place is held!"
    )
  })

  it("should pass defaultOptions to AsyncSelect", () => {
    const wrapper = render({
      defaultOptions: "options",
      loadOptions:    () => null
    })
    expect(wrapper.find(AsyncSelect).prop("defaultOptions")).toBe("options")
  })

  it("should use AsyncSelect if a loadOptions callback is supplied", () => {
    const loadOptions = sandbox.stub()
    const wrapper = render({
      loadOptions
    })

    const select = wrapper.find(AsyncSelect)
    expect(select.exists()).toBeTruthy()

    expect(select.prop("loadOptions")).toBe(loadOptions)
  })

  describe("not multiple choice", () => {
    it("renders a select widget", () => {
      const value = "initial"
      const wrapper = render({
        value
      })
      const props = wrapper.find(Select).props()
      expect(props.value).toStrictEqual({
        label: value,
        value: value
      })
      expect(props.isMulti).toBeFalsy()
      expect(props.options).toStrictEqual(expectedOptions)

      const newValue = "newValue"
      props.onChange({ value: newValue })
      sinon.assert.calledWith(onChangeStub, {
        target: { value: newValue, name: name }
      })
    })

    it("handles an empty value gracefully", () => {
      const wrapper = render({
        value: null
      })
      const props = wrapper.find(Select).props()
      expect(props.value).toBeNull()
    })
  })

  describe("multiple choice", () => {
    it("renders a select widget", () => {
      const value = ["initial", "values", "3", "4"]
      const expectedValue = [
        { label: "initial", value: "initial" },
        { label: "values", value: "values" },
        { label: "Three", value: "3" },
        { label: "4", value: "4" }
      ]
      const wrapper = render({
        value,
        multiple: true
      })
      const props = wrapper.find(Select).props()
      expect(props.value).toStrictEqual(expectedValue)
      expect(props.isMulti).toBeTruthy()
      expect(props.options).toStrictEqual(expectedOptions)

      const newValue = ["newValue", "value2"]
      props.onChange(newValue.map(_value => ({ value: _value })))
      sinon.assert.calledWith(onChangeStub, {
        target: { value: newValue, name: name }
      })
    })

    it("handles an empty value gracefully", () => {
      const wrapper = render({
        value:    null,
        multiple: true
      })
      const props = wrapper.find(Select).props()
      expect(props.value).toStrictEqual([])
    })
  })
})
