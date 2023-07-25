import { act } from "react-dom/test-utils"
import { DndContext } from "@dnd-kit/core"
import casual from "casual"

import IntegrationTestHelper, {
  TestRenderer
} from "../../util/integration_test_helper_old"
import SortableSelect, { SortableItem } from "./SortableSelect"
import { Option } from "./SelectField"
import { zip } from "ramda"
import { default as SortableItemComponent } from "../SortableItem"
import { triggerSortableSelect } from "./test_util"
import SelectField from "./SelectField"

const createFakeOptions = (times: number): Option[] =>
  Array(times)
    .fill(0)
    .map(() => ({
      value: casual.uuid,
      label: casual.title
    }))

describe("SortableSelect", () => {
  let render: TestRenderer,
    helper: IntegrationTestHelper,
    options: Option[],
    onChange: jest.Mock,
    newOptions: Option[],
    loadOptions: jest.Mock

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    options = createFakeOptions(10)
    newOptions = createFakeOptions(10)
    onChange = jest.fn()
    loadOptions = jest.fn().mockReturnValue({ options: newOptions })
    render = helper.configureRenderer(SortableSelect, {
      options,
      onChange,
      loadOptions,
      name:  "test-select",
      value: []
    })
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("should pass options down to the SelectField", async () => {
    const { wrapper } = await render()
    expect(wrapper.find("SelectField").prop("options")).toStrictEqual(options)
  })

  it("should pass isOptionDisabled down to the SelectField", async () => {
    const isOptionDisabled = jest.fn()
    const { wrapper } = await render({ isOptionDisabled })
    expect(wrapper.find(SelectField).prop("isOptionDisabled")).toBe(
      isOptionDisabled
    )
  })

  it("should render sortable items for the current value", async () => {
    const value: SortableItem[] = options.map(option => ({
      id:    option.value,
      title: option.label
    }))

    const { wrapper } = await render({
      value
    })

    zip(value, [...(wrapper.find(SortableItemComponent) as any)]).forEach(
      ([value, sortableItem]) => {
        expect(sortableItem.props["title"]).toBe(value.title)
        expect(sortableItem.props["id"]).toBe(value.id)
        expect(sortableItem.props["item"]).toBe(value.id)
      }
    )
  })

  it("should allow adding another element", async () => {
    const { wrapper } = await render()
    await triggerSortableSelect(wrapper, newOptions[0].label)
    expect(onChange).toHaveBeenCalledWith([newOptions[0].label])
    expect(wrapper.find("SelectField").prop("value")).toBeUndefined()
  })

  it("should let you drag and drop items to reorder", async () => {
    const value: SortableItem[] = options.slice(0, 3).map(option => ({
      id:    option.value,
      title: option.label
    }))

    const { wrapper } = await render({
      value
    })

    act(() => {
      wrapper.find(DndContext)!.prop("onDragEnd")!({
        active: { id: value[2].id },
        over:   { id: value[0].id }
      } as any)
    })
    expect(onChange).toHaveBeenCalledWith([
      value[2].id,
      value[0].id,
      value[1].id
    ])
  })
})
