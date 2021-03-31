import React from "react"
import sinon, { SinonSandbox, SinonStub } from "sinon"
import { shallow } from "enzyme"
import Select from "react-select"

import SelectField, { Option } from "./SelectField"

describe("SelectField", () => {
  let sandbox: SinonSandbox,
    onChangeStub: SinonStub,
    name: string,
    options: string[],
    expectedOptions: Option[],
    min: number,
    max: number

  beforeEach(() => {
    sandbox = sinon.createSandbox()
    onChangeStub = sandbox.stub()
    options = ["one", "two"]
    expectedOptions = [
      { label: "one", value: "one" },
      { label: "two", value: "two" }
    ]
    min = 1
    max = 3
  })

  afterEach(() => {
    sandbox.restore()
  })

  const render = (props: any) =>
    shallow(
      <SelectField
        onChange={onChangeStub}
        name={name}
        min={min}
        max={max}
        options={options}
        {...props}
      />
    )

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
      const value = ["initial", "values"]
      const wrapper = render({
        value,
        multiple: true
      })
      const props = wrapper.find(Select).props()
      expect(props.value).toStrictEqual(
        value.map(_value => ({ label: _value, value: _value }))
      )
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
