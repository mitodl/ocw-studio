import React from "react"
import { act } from "react-dom/test-utils"
import { sortBy, times } from "lodash"
import { shallow, ShallowWrapper } from "enzyme"
import casual from "casual"

import HierarchicalSelectField, {
  calcOptions,
  Level
} from "./HierarchicalSelectField"
import SelectField, { Option } from "./SelectField"

const simulateSelectValue = (
  wrapper: ShallowWrapper,
  value: string,
  idx: number
) => {
  return act(() => {
    wrapper
      .find(SelectField)
      .at(idx)
      .prop("onChange")({
      // @ts-expect-error not simulating whole event
        target: { value }
      })
  })
}

describe("HierarchicalSelectField", () => {
  let render: (props?: any) => ShallowWrapper,
    name: string,
    levels: Array<Level>,
    value: any,
    onChangeStub: typeof jest.fn,
    optionsMap: any,
    options: Option[][]

  const makeOptions = (idx: number) => [
    { label: "Empty", value: "" },
    { label: `Option 1 for ${idx}`, value: `option1${idx}` },
    { label: `Option 2 for ${idx}`, value: `option2${idx}` }
  ]

  const selectPath = [
    { label: "Topic1", value: "Topic1" },
    { label: "Subtopic1", value: "Subtopic1" },
    { label: "speciality", value: "speciality" }
  ]

  beforeEach(() => {
    name = casual.name
    levels = times(3, () => ({
      name:  casual.name,
      label: casual.word
    }))
    options = times(levels.length, makeOptions)
    value = null
    onChangeStub = jest.fn()
    optionsMap = {
      Topic1: {
        Subtopic1: ["speciality"],
        Subtopic2: ["potato"]
      },
      Topic2: {}
    }

    options = [
      [
        { label: "-- empty --", value: "" },
        { label: "Topic1", value: "Topic1" },
        { label: "Topic2", value: "Topic2" }
      ],
      [{ label: "-- empty --", value: "" }],
      [{ label: "-- empty --", value: "" }]
    ]
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
      simulateSelectValue(wrapper, selectPath[idx].value, idx)
      expect(
        wrapper
          .find("SelectField")
          .at(idx)
          .prop("value")
      ).toBe(selectPath[idx].value)
    }
  })

  it("resets values on deeper levels when a value is set", () => {
    const wrapper = render()
    for (let idx = 0; idx < levels.length; ++idx) {
      simulateSelectValue(wrapper, selectPath[idx].value, idx)
    }
    simulateSelectValue(wrapper, "Topic2", 0)
    expect(
      wrapper
        .find("SelectField")
        .at(0)
        .prop("value")
    ).toBe("Topic2")
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
      simulateSelectValue(wrapper, selectPath[idx].value, idx)
    }
    const lastIdx = levels.length - 1
    simulateSelectValue(wrapper, "potato", lastIdx)
    expect(
      wrapper
        .find("SelectField")
        .at(lastIdx)
        .prop("value")
    ).toBe("potato")
    for (let idx = 0; idx < lastIdx; ++idx) {
      expect(
        wrapper
          .find("SelectField")
          .at(idx)
          .prop("value")
      ).toBe(selectPath[idx].value)
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
      // @ts-expect-error Not simulating the whole event
      button.prop("onClick")(event)
      expect(event.preventDefault).toHaveBeenCalled()
      expect(onChangeStub).toHaveBeenCalledWith({
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
      const value = [[duplicate ? "Topic2" : "Topic1"], ["Topic2", "Subtopic"]]
      const wrapper = render({
        value
      })
      simulateSelectValue(wrapper, "Topic2", 0)

      const event = { preventDefault: jest.fn() }
      // @ts-expect-error Not simulating the whole event
      wrapper.find(".add").prop("onClick")(event)

      expect(event.preventDefault).toHaveBeenCalled()
      expect(onChangeStub).toHaveBeenCalledWith({
        target: {
          value: sortBy(duplicate ? value : [...value, ["Topic2"]]),
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
    // @ts-expect-error Not simulating the whole event
    wrapper.find(".add").prop("onClick")(event)

    expect(event.preventDefault).toHaveBeenCalled()
    expect(onChangeStub).not.toHaveBeenCalled()
  })

  describe("calcOptions", () => {
    const emptyOption = { label: "-- empty --", value: "" }

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
