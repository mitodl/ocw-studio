import React from "react"
import sinon, { SinonSandbox, SinonStub } from "sinon"
import { ReactWrapper, mount } from "enzyme"
import Select from "react-select"
import { AsyncPaginate, LoadOptions } from "react-select-async-paginate"
import AsyncSelect from "react-select/async"

import SelectField, { Additional, Option } from "./SelectField"
import { act } from "react-dom/test-utils"
import { triggerSelectMenu } from "./test_util"

describe("SelectField", () => {
  let sandbox: SinonSandbox,
    onChangeStub: SinonStub,
    name: string,
    options: Array<string | Option>,
    loadOptions: LoadOptions<Option, Option, Additional>,
    expectedOptions: Option[],
    classNamePrefix: string,
    min: number,
    max: number

  beforeEach(() => {
    sandbox = sinon.createSandbox()
    onChangeStub = sandbox.stub()
    loadOptions = jest.fn().mockReturnValue({ options: [] })
    options = ["one", "two", { label: "Three", value: "3" }]
    expectedOptions = [
      { label: "one", value: "one" },
      { label: "two", value: "two" },
      { label: "Three", value: "3" },
    ]
    classNamePrefix = "select"
    min = 1
    max = 3
  })

  afterEach(() => {
    sandbox.restore()
  })

  const render = async (props: any = {}) => {
    let wrapper: ReactWrapper

    await act(async () => {
      wrapper = mount(
        <SelectField
          onChange={onChangeStub}
          name={name}
          min={min}
          max={max}
          options={options}
          classNamePrefix={classNamePrefix}
          {...props}
        />,
      )
    })

    return wrapper!
  }

  it("should pass placeholder to Select", async () => {
    const wrapper = await render({
      placeholder: "This place is held!",
    })
    expect(wrapper.find("Select").prop("placeholder")).toBe(
      "This place is held!",
    )
  })
  ;[true, false].forEach((isInfiniteScroll) =>
    it(`should pass defaultOptions to ${
      isInfiniteScroll ? "AsyncPaginate" : "AsyncSelect"
    }`, async () => {
      SETTINGS.features.SELECT_FIELD_INFINITE_SCROLL = isInfiniteScroll

      const wrapper = await render({
        defaultOptions: "options",
        loadOptions,
      })

      expect(
        wrapper
          .find(isInfiniteScroll ? AsyncPaginate : AsyncSelect)
          .prop("defaultOptions"),
      ).toBe("options")
    }),
  )

  it("should pass isOptionDisabled down to the Select", async () => {
    const isOptionDisabled = jest.fn()
    const wrapper = await render({ isOptionDisabled })
    expect(wrapper.find(Select).prop("isOptionDisabled")).toBe(isOptionDisabled)
  })
  ;[true, false].forEach((isInfiniteScroll) =>
    it(`should pass isOptionDisabled down to the ${
      isInfiniteScroll ? "AsyncPaginate" : "AsyncSelect"
    }`, async () => {
      SETTINGS.features.SELECT_FIELD_INFINITE_SCROLL = isInfiniteScroll

      const isOptionDisabled = jest.fn()
      const wrapper = await render({
        isOptionDisabled,
        loadOptions,
      })
      expect(
        wrapper
          .find(isInfiniteScroll ? AsyncPaginate : AsyncSelect)
          .prop("isOptionDisabled"),
      ).toBe(isOptionDisabled)
    }),
  )

  it("should use AsyncPaginate if a loadOptions callback is supplied and infinite scroll is enabled", async () => {
    SETTINGS.features.SELECT_FIELD_INFINITE_SCROLL = true

    const wrapper = await render({
      loadOptions,
    })

    const select = wrapper.find(AsyncPaginate)
    expect(select.exists()).toBeTruthy()

    expect(select.prop("loadOptions")).toBe(loadOptions)
  })

  it.each(["select", "async-select", "async-paginate"])(
    "should render options in menu",
    async (component) => {
      SETTINGS.features.SELECT_FIELD_INFINITE_SCROLL =
        component === "async-paginate"

      const wrapper = await render({
        loadOptions: component !== "select" ? loadOptions : undefined,
        defaultOptions: options,
      })

      await triggerSelectMenu(wrapper)

      const renderedOptions = wrapper
        .find(`.${classNamePrefix}__option`)
        .hostNodes()
        .map((x) => x.text())

      const expectedOptions = options.map(
        (x) => (x as Option).label ?? (component !== "select" ? "" : x),
      )

      expect(renderedOptions).toEqual(expectedOptions)
    },
  )

  it("should preserve search text on menu close", async () => {
    const searchText = "An"
    const wrapper = await render({
      preserveSearchText: true,
    })

    await triggerSelectMenu(wrapper)

    await act(async () => {
      wrapper.find(Select).prop("onInputChange")(searchText, {
        reason: "test",
      })
    })

    // Close and open the menu again
    await triggerSelectMenu(wrapper)
    await triggerSelectMenu(wrapper)

    const value = wrapper.find("input").hostNodes().prop("value")
    expect(value).toEqual(searchText)
  })

  it("should preserve search text on option selection", async () => {
    const searchText = "An"
    const wrapper = await render({
      preserveSearchText: true,
    })

    await triggerSelectMenu(wrapper)

    await act(async () => {
      wrapper.find(Select).prop("onInputChange")(searchText, {
        reason: "test",
      })
    })

    // select an option.
    await act(async () => {
      wrapper
        .find(`.${classNamePrefix}__option`)
        .hostNodes()
        .first()
        .simulate("click")
    })
    wrapper.update()

    // Open the menu again because selection closes it.
    await triggerSelectMenu(wrapper)

    const value = wrapper.find("input").hostNodes().prop("value")
    expect(value).toEqual(searchText)
  })

  it("should pass isOptionSelected down to the Select", async () => {
    const isOptionSelected = jest.fn()
    const wrapper = await render({ isOptionSelected })
    expect(wrapper.find(Select).prop("isOptionSelected")).toBe(isOptionSelected)
  })

  it("should only show unselected menu items when hideSelectedOptions is true", async () => {
    const wrapper = await render({
      hideSelectedOptions: true,
      options: [
        {
          label: "Not selected",
          value: "not-selected",
        },
        {
          label: "Selected",
          value: "selected",
        },
      ],
      value: "selected",
    })

    await triggerSelectMenu(wrapper)

    const selectedNode = wrapper
      .find(`.${classNamePrefix}__option`)
      .find({ children: "Selected" })
    const notSelectedNode = wrapper
      .find(`.${classNamePrefix}__option`)
      .find({ children: "Not selected" })

    expect(selectedNode.exists()).toBeFalsy()
    expect(notSelectedNode.exists()).toBeTruthy()
  })

  describe("not multiple choice", () => {
    it("renders a select widget", async () => {
      const value = "initial"
      const wrapper = await render({
        value,
      })
      const props = wrapper.find(Select).props()
      expect(props.value).toStrictEqual({
        label: value,
        value: value,
      })
      expect(props.isMulti).toBeFalsy()
      expect(props.options).toStrictEqual(expectedOptions)

      const newValue = "newValue"
      props.onChange({ value: newValue })
      sinon.assert.calledWith(onChangeStub, {
        target: { value: newValue, name: name },
      })
    })

    it("handles an empty value gracefully", async () => {
      const wrapper = await render({
        value: null,
      })
      const props = wrapper.find(Select).props()
      expect(props.value).toBeNull()
    })
  })

  describe("multiple choice", () => {
    it("renders a select widget", async () => {
      const value = ["initial", "values", "3", "4"]
      const expectedValue = [
        { label: "initial", value: "initial" },
        { label: "values", value: "values" },
        { label: "Three", value: "3" },
        { label: "4", value: "4" },
      ]
      const wrapper = await render({
        value,
        multiple: true,
      })
      const props = wrapper.find(Select).props()
      expect(props.value).toStrictEqual(expectedValue)
      expect(props.isMulti).toBeTruthy()
      expect(props.options).toStrictEqual(expectedOptions)

      const newValue = ["newValue", "value2"]
      props.onChange(newValue.map((_value) => ({ value: _value })))
      sinon.assert.calledWith(onChangeStub, {
        target: { value: newValue, name: name },
      })
    })

    it("handles an empty value gracefully", async () => {
      const wrapper = await render({
        value: null,
        multiple: true,
      })
      const props = wrapper.find(Select).props()
      expect(props.value).toStrictEqual([])
    })
  })
})
