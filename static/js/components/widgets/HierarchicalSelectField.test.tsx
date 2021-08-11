import React from "react"
import { act } from "react-dom/test-utils"
import { sortBy, times } from "lodash"
import { shallow, ShallowWrapper } from "enzyme"
import casual from "casual-browserify"

import HierarchicalSelectField, * as namedExports from "./HierarchicalSelectField"
import { Level } from "./HierarchicalSelectField"
import { Option } from "./SelectField"

describe("HierarchicalSelectField", () => {
  let render: (props?: any) => ShallowWrapper,
    name: string,
    levels: Array<Level>,
    value: any,
    onChangeStub: typeof jest.fn,
    optionsMap: any,
    options: Option[][],
    spyCalcOptions: jest.MockedFunction<any>

  const makeOptions = (idx: number) => [
    { label: "Empty", value: "" },
    { label: `Option 1 for ${idx}`, value: `option1${idx}` },
    { label: `Option 2 for ${idx}`, value: `option2${idx}` }
  ]

  beforeEach(() => {
    spyCalcOptions = jest.spyOn(namedExports, "calcOptions")

    name = casual.name
    levels = times(3, () => ({
      name:  casual.name,
      label: casual.word
    }))
    options = times(levels.length, makeOptions)
    spyCalcOptions.mockReturnValue(options)
    value = null
    onChangeStub = jest.fn()
    optionsMap = {
      Topic1: {
        Subtopic1: ["speciality"],
        Subtopic2: []
      },
      Topic2: {}
    }
    render = (props = {}) =>
      shallow(
        <HierarchicalSelectField
          name={name}
          levels={levels}
          value={value}
          onChange={onChangeStub}
          options_map={optionsMap}
          {...props}
        />
      )
  })

  afterEach(() => {
    spyCalcOptions.mockRestore()
  })

  it("renders a select field for each level", () => {
    const wrapper = render()
    expect(wrapper.find("SelectField")).toHaveLength(levels.length)
    for (let idx = 0; idx < levels.length; ++idx) {
      const select = wrapper.find("SelectField").at(idx)
      expect(select.prop("name")).toBe(levels[idx].name)
      expect(select.prop("placeholder")).toBe(levels[idx].label)
      expect(select.prop("options")).toStrictEqual(options[idx])
      expect(select.prop("value")).toBeNull()
    }
  })

  it("shows nothing in the list of values if there is no value", () => {
    const wrapper = render({ value: undefined })
    expect(wrapper.find(".values").text()).toBe("")
  })

  it("selects a value", () => {
    const wrapper = render()
    for (let idx = 0; idx < levels.length; ++idx) {
      act(() => {
        // @ts-ignore
        wrapper
          .find("SelectField")
          .at(idx)
          // @ts-ignore
          .prop("onChange")({ target: { value: options[idx][1].value } })
      })
      expect(
        wrapper
          .find("SelectField")
          .at(idx)
          .prop("value")
      ).toBe(options[idx][1].value)
    }
  })

  it("resets values on deeper levels when a value is set", () => {
    const wrapper = render()
    for (let idx = 0; idx < levels.length; ++idx) {
      act(() => {
        // @ts-ignore
        wrapper
          .find("SelectField")
          .at(idx)
          // @ts-ignore
          .prop("onChange")({ target: { value: options[idx][1].value } })
      })
    }
    act(() => {
      // @ts-ignore
      wrapper
        .find("SelectField")
        .at(0)
        // @ts-ignore
        .prop("onChange")({ target: { value: options[0][2].value } })
    })
    expect(
      wrapper
        .find("SelectField")
        .at(0)
        .prop("value")
    ).toBe(options[0][2].value)
    for (let idx = 1; idx < levels.length; ++idx) {
      expect(
        wrapper
          .find("SelectField")
          .at(idx)
          .prop("value")
      ).toBeNull()
    }
  })

  it("keeps selection on higher levels when a value is set at a deeper one", () => {
    const wrapper = render()
    for (let idx = 0; idx < levels.length; ++idx) {
      act(() => {
        // @ts-ignore
        wrapper
          .find("SelectField")
          .at(idx)
          // @ts-ignore
          .prop("onChange")({ target: { value: options[idx][1].value } })
      })
    }
    const lastIdx = levels.length - 1
    act(() => {
      // @ts-ignore
      wrapper
        .find("SelectField")
        .at(lastIdx)
        // @ts-ignore
        .prop("onChange")({ target: { value: options[lastIdx][2].value } })
    })
    expect(
      wrapper
        .find("SelectField")
        .at(lastIdx)
        .prop("value")
    ).toBe(options[lastIdx][2].value)
    for (let idx = 0; idx < lastIdx; ++idx) {
      expect(
        wrapper
          .find("SelectField")
          .at(idx)
          .prop("value")
      ).toBe(options[idx][1].value)
    }
  })

  //
  ;[true, false].forEach(hasValue => {
    it(`renders the current value${hasValue ? ", which is empty" : ""}`, () => {
      const value = hasValue ? [["Topic1"], ["Topic2", "Subtopic"]] : undefined
      const wrapper = render({ value })
      expect(wrapper.find(".values div").map(div => div.text())).toStrictEqual(
        hasValue ? ["Topic1delete", "Topic2 - Subtopicdelete"] : []
      )
    })
  })

  //
  ;[0, 1].forEach(valueIndex => {
    it(`deletes a value at index ${valueIndex}`, () => {
      const value = [["Topic1"], ["Topic2", "Subtopic"]]
      const wrapper = render({ value })

      const button = wrapper.find(".values div button").at(valueIndex)
      expect(button.text()).toBe("delete")
      const event = { preventDefault: jest.fn() }
      // @ts-ignore
      button.prop("onClick")(event)
      expect(event.preventDefault).toBeCalled()
      expect(onChangeStub).toBeCalledWith({
        target: {
          name,
          value: [value[valueIndex === 0 ? 1 : 0]]
        }
      })
    })
  })

  //
  ;[true, false].forEach(duplicate => {
    it(`adds the selection as a new value${
      duplicate ? ", but it's a duplicate value so it's ignored" : ""
    }`, () => {
      const value = [
        [duplicate ? options[0][1].value : "Topic1"],
        ["Topic2", "Subtopic"]
      ]
      const wrapper = render({
        value
      })
      act(() => {
        // @ts-ignore
        wrapper
          .find("SelectField")
          .at(0)
          // @ts-ignore
          .prop("onChange")({ target: { value: options[0][1].value } })
      })

      const event = { preventDefault: jest.fn() }
      // @ts-ignore
      wrapper.find(".add").prop("onClick")(event)

      expect(event.preventDefault).toBeCalled()
      expect(onChangeStub).toBeCalledWith({
        target: {
          value: sortBy(duplicate ? value : [...value, [options[0][1].value]]),
          name
        }
      })
    })
  })

  it("ignores an empty selection", () => {
    const value = [["Topic1"], ["Topic2", "Subtopic"]]
    const wrapper = render({
      value
    })

    const event = { preventDefault: jest.fn() }
    // @ts-ignore
    wrapper.find(".add").prop("onClick")(event)

    expect(event.preventDefault).toBeCalled()
    expect(onChangeStub).not.toBeCalled()
  })

  describe.only("calcOptions", () => {
    let calcOptions: any
    const emptyOption = { label: "-- empty --", value: "" }

    beforeEach(() => {
      spyCalcOptions.mockRestore()
      calcOptions = namedExports.calcOptions
    })

    it("returns options if there is no selection", () => {
      const selection = [null, null, null]
      const options = calcOptions(optionsMap, selection, levels)
      expect(options).toStrictEqual([
        [
          emptyOption,
          { label: "Topic1", value: "Topic1" },
          { label: "Topic2", value: "Topic2" }
        ],
        [emptyOption],
        [emptyOption]
      ])
    })

    it("returns options if the first item is selected", () => {
      const selection = ["Topic1", null, null]
      const options = calcOptions(optionsMap, selection, levels)
      expect(options).toStrictEqual([
        [
          emptyOption,
          { label: "Topic1", value: "Topic1" },
          { label: "Topic2", value: "Topic2" }
        ],
        [
          emptyOption,
          { label: "Subtopic1", value: "Subtopic1" },
          { label: "Subtopic2", value: "Subtopic2" }
        ],
        [emptyOption]
      ])
    })

    //
    ;[true, false].forEach(hasThirdSelected => {
      it(`returns options if the second ${
        hasThirdSelected ? " and third" : ""
      }item is selected`, () => {
        const selection = [
          "Topic1",
          "Subtopic1",
          hasThirdSelected ? "speciality" : null
        ]
        const options = calcOptions(optionsMap, selection, levels)
        expect(options).toStrictEqual([
          [
            { label: "-- empty --", value: "" },
            { label: "Topic1", value: "Topic1" },
            { label: "Topic2", value: "Topic2" }
          ],
          [
            { label: "-- empty --", value: "" },
            { label: "Subtopic1", value: "Subtopic1" },
            {
              label: "Subtopic2",
              value: "Subtopic2"
            }
          ],
          [
            { label: "-- empty --", value: "" },
            { label: "speciality", value: "speciality" }
          ]
        ])
      })
    })
  })
})
