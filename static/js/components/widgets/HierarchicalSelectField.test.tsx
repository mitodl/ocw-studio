import React from "react"
import { sortBy } from "lodash"
import casual from "casual"
import { render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import HierarchicalSelectField, {
  calcOptions,
  Level,
} from "./HierarchicalSelectField"

describe("HierarchicalSelectField", () => {
  let name: string,
    levels: Array<Level>,
    value: any,
    onChangeStub: typeof jest.fn,
    optionsMap: any

  beforeEach(() => {
    name = casual.name
    levels = [
      { name: "level0", label: "Level 0" },
      { name: "level1", label: "Level 1" },
      { name: "level2", label: "Level 2" },
    ]
    value = null
    onChangeStub = jest.fn()
    optionsMap = {
      Topic1: {
        Subtopic1: ["speciality"],
        Subtopic2: ["potato"],
      },
      Topic2: {},
    }
  })

  const renderField = (props = {}) =>
    render(
      <HierarchicalSelectField
        name={name}
        levels={levels}
        value={value}
        onChange={onChangeStub}
        options_map={optionsMap}
        {...props}
      />,
    )

  const openSelectAndChoose = async (
    user: ReturnType<typeof userEvent.setup>,
    levelLabel: string,
    optionLabel: string,
  ) => {
    const input = screen.getByLabelText(levelLabel)
    await user.click(input)
    const menu = document.querySelector("[class*='-menu']")
    const option = within(menu as HTMLElement).getByText(optionLabel)
    await user.click(option)
  }

  it("renders a select field for each level", () => {
    renderField()
    for (let idx = 0; idx < levels.length; ++idx) {
      expect(screen.getByLabelText(levels[idx].label)).toBeInTheDocument()
    }
  })

  it("shows nothing in the list of values if there is no value", () => {
    renderField({ value: undefined })
    expect(
      screen.queryByRole("button", { name: "delete" }),
    ).not.toBeInTheDocument()
  })

  it("selects a value", async () => {
    const user = userEvent.setup()
    renderField()

    await openSelectAndChoose(user, levels[0].label, "Topic1")
    await openSelectAndChoose(user, levels[1].label, "Subtopic1")
    await openSelectAndChoose(user, levels[2].label, "speciality")

    expect(screen.getByText("speciality")).toBeInTheDocument()
  })

  it("resets values on deeper levels when a value is set", async () => {
    const user = userEvent.setup()
    renderField()

    await openSelectAndChoose(user, levels[0].label, "Topic1")
    await openSelectAndChoose(user, levels[1].label, "Subtopic1")
    await openSelectAndChoose(user, levels[2].label, "speciality")

    await openSelectAndChoose(user, levels[0].label, "Topic2")

    expect(screen.getByText("Topic2")).toBeInTheDocument()
  })

  it("keeps selection on higher levels when a value is set at a deeper one", async () => {
    const user = userEvent.setup()
    renderField()

    await openSelectAndChoose(user, levels[0].label, "Topic1")
    await openSelectAndChoose(user, levels[1].label, "Subtopic1")
    await openSelectAndChoose(user, levels[2].label, "speciality")

    expect(screen.getByText("Topic1")).toBeInTheDocument()
    expect(screen.getByText("Subtopic1")).toBeInTheDocument()
  })

  //
  ;[true, false].forEach((hasValue) => {
    it(`renders the current value${hasValue ? ", which is empty" : ""}`, () => {
      const value = hasValue ? [["Topic1"], ["Topic2", "Subtopic"]] : undefined
      renderField({ value })
      const valuesContainer = screen.getByRole("list", {
        name: "Selected values",
      })
      if (hasValue) {
        expect(valuesContainer).toHaveTextContent("Topic1")
        expect(valuesContainer).toHaveTextContent("Topic2 - Subtopic")
      } else {
        expect(valuesContainer).toHaveTextContent("")
      }
    })
  })

  //
  ;[0, 1].forEach((valueIndex) => {
    it(`deletes a value at index ${valueIndex}`, async () => {
      const user = userEvent.setup()
      const value = [["Topic1"], ["Topic2", "Subtopic"]]
      renderField({ value })

      const deleteButtons = screen.getAllByRole("button", { name: "delete" })
      await user.click(deleteButtons[valueIndex])

      expect(onChangeStub).toHaveBeenCalledWith({
        target: {
          name,
          value: [value[valueIndex === 0 ? 1 : 0]],
        },
      })
    })
  })

  //
  ;[true, false].forEach((duplicate) => {
    it(`adds the selection as a new value${
      duplicate ? ", but it's a duplicate value so it's ignored" : ""
    }`, async () => {
      const user = userEvent.setup()
      const value = [[duplicate ? "Topic2" : "Topic1"], ["Topic2", "Subtopic"]]
      renderField({ value })

      await openSelectAndChoose(user, levels[0].label, "Topic2")

      const addButton = screen.getByRole("button", { name: "Add" })
      await user.click(addButton)

      expect(onChangeStub).toHaveBeenCalledWith({
        target: {
          value: sortBy(duplicate ? value : [...value, ["Topic2"]]),
          name,
        },
      })
    })
  })

  it("ignores an empty selection", async () => {
    const user = userEvent.setup()
    const value = [["Topic1"], ["Topic2", "Subtopic"]]
    renderField({ value })

    const addButton = screen.getByRole("button", { name: "Add" })
    await user.click(addButton)

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
          { label: "Topic2", value: "Topic2" },
        ],
        [emptyOption],
        [emptyOption],
      ])
    })

    it("returns options if the first item is selected", () => {
      const selection = ["Topic1", null, null]
      const options = calcOptions(optionsMap, selection, levels)
      expect(options).toStrictEqual([
        [
          emptyOption,
          { label: "Topic1", value: "Topic1" },
          { label: "Topic2", value: "Topic2" },
        ],
        [
          emptyOption,
          { label: "Subtopic1", value: "Subtopic1" },
          { label: "Subtopic2", value: "Subtopic2" },
        ],
        [emptyOption],
      ])
    })

    //
    ;[true, false].forEach((hasThirdSelected) => {
      it(`returns options if the second ${
        hasThirdSelected ? " and third" : ""
      }item is selected`, () => {
        const selection = [
          "Topic1",
          "Subtopic1",
          hasThirdSelected ? "speciality" : null,
        ]
        const options = calcOptions(optionsMap, selection, levels)
        expect(options).toStrictEqual([
          [
            { label: "-- empty --", value: "" },
            { label: "Topic1", value: "Topic1" },
            { label: "Topic2", value: "Topic2" },
          ],
          [
            { label: "-- empty --", value: "" },
            { label: "Subtopic1", value: "Subtopic1" },
            {
              label: "Subtopic2",
              value: "Subtopic2",
            },
          ],
          [
            { label: "-- empty --", value: "" },
            { label: "speciality", value: "speciality" },
          ],
        ])
      })
    })
  })
})
