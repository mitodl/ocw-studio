import { act } from "react-dom/test-utils"
import sinon, { SinonStub } from "sinon"
import { DndContext } from "@dnd-kit/core"
import casual from "casual"

import IntegrationTestHelper, {
  TestRenderer
} from "../../util/integration_test_helper"
import SortableSelect, { SortableItem } from "./SortableSelect"
import { Option } from "./SelectField"
import { zip } from "ramda"
import { default as SortableItemComponent } from "../SortableItem"

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
    onChange: SinonStub,
    newOptions: Option[],
    loadOptions: SinonStub

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    options = createFakeOptions(10)
    newOptions = createFakeOptions(10)
    onChange = helper.sandbox.stub()
    loadOptions = helper.sandbox.stub().resolves(newOptions)
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
    await act(async () => {
      // @ts-ignore
      wrapper.find("SelectField").prop("onChange")({
        // @ts-ignore
        target: { value: newOptions[0].label }
      })
    })
    wrapper.update()
    wrapper.find(".cyan-button").simulate("click")
    sinon.assert.calledWith(onChange, [newOptions[0].label])
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
    sinon.assert.calledWith(onChange, [value[2].id, value[0].id, value[1].id])
  })
})
