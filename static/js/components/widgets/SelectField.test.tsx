import React from "react"
import sinon, { SinonSandbox } from "sinon"
import { shallow } from "enzyme"
import Select from "react-select"

import SelectField from "./SelectField"

describe("SelectField", () => {
  let sandbox: SinonSandbox

  beforeEach(() => {
    sandbox = sinon.createSandbox()
  })

  afterEach(() => {
    sandbox.restore()
  })

  describe("not multiple choice", () => {
    it("renders a select widget", () => {
      const initialValue = "initial"
      const name = "name"
      const options = ["one", "two"]
      const expectedOptions = [
        { label: "one", value: "one" },
        { label: "two", value: "two" }
      ]

      const onChangeStub = sandbox.stub()

      const wrapper = shallow(
        <SelectField
          value={initialValue}
          name={name}
          onChange={onChangeStub}
          options={options}
        />
      )
      const props = wrapper.find(Select).props()
      expect(props.value).toStrictEqual({
        label: initialValue,
        value: initialValue
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
      const name = "name"
      const options = ["one", "two"]

      const wrapper = shallow(
        <SelectField
          value={null}
          name={name}
          onChange={sandbox.stub()}
          options={options}
        />
      )
      const props = wrapper.find(Select).props()
      expect(props.value).toBeNull()
    })
  })

  describe("multiple choice", () => {
    it("renders a select widget", () => {
      const initialValue = ["initial", "values"]
      const name = "name"
      const options = ["one", "two"]
      const expectedOptions = [
        { label: "one", value: "one" },
        { label: "two", value: "two" }
      ]
      const min = 1
      const max = 3

      const onChangeStub = sandbox.stub()

      const wrapper = shallow(
        <SelectField
          value={initialValue}
          name={name}
          onChange={onChangeStub}
          options={options}
          multiple={true}
          min={min}
          max={max}
        />
      )
      const props = wrapper.find(Select).props()
      expect(props.value).toStrictEqual(
        initialValue.map(_value => ({ label: _value, value: _value }))
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
      const name = "name"
      const options = ["one", "two"]

      const wrapper = shallow(
        <SelectField
          value={null}
          name={name}
          onChange={sandbox.stub()}
          options={options}
          multiple={true}
        />
      )
      const props = wrapper.find(Select).props()
      expect(props.value).toStrictEqual([])
    })
  })
})
