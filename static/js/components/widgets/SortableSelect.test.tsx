import React from "react"
import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import casual from "casual"

import SortableSelect, { SortableItem } from "./SortableSelect"
import { Option } from "./SelectField"

jest.mock("@dnd-kit/core", () => {
  const actual = jest.requireActual("@dnd-kit/core")
  return {
    ...actual,
    DndContext: ({
      children,
      onDragEnd,
    }: {
      children: React.ReactNode
      onDragEnd: (event: any) => void
    }) => {
      ;(global as any).__testOnDragEnd = onDragEnd
      return <>{children}</>
    },
    closestCenter: jest.fn(),
    KeyboardSensor: jest.fn(),
    PointerSensor: jest.fn(),
    useSensor: jest.fn(),
    useSensors: jest.fn(() => []),
  }
})

jest.mock("@dnd-kit/sortable", () => ({
  SortableContext: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
  verticalListSortingStrategy: jest.fn(),
  useSortable: () => ({
    attributes: {},
    listeners: {},
    setNodeRef: jest.fn(),
    transform: null,
    transition: null,
  }),
  arrayMove: (array: any[], from: number, to: number) => {
    const newArray = [...array]
    const [removed] = newArray.splice(from, 1)
    newArray.splice(to, 0, removed)
    return newArray
  },
}))

const createFakeOptions = (times: number): Option[] =>
  Array(times)
    .fill(0)
    .map(() => ({
      value: casual.uuid,
      label: casual.title,
    }))

describe("SortableSelect", () => {
  let options: Option[],
    onChange: jest.Mock,
    newOptions: Option[],
    loadOptions: jest.Mock

  beforeEach(() => {
    options = createFakeOptions(10)
    newOptions = createFakeOptions(10)
    onChange = jest.fn()
    loadOptions = jest.fn().mockReturnValue({ options: newOptions })
  })

  const renderSortableSelect = (
    props: Partial<React.ComponentProps<typeof SortableSelect>> = {},
  ) => {
    return render(
      <SortableSelect
        options={options}
        onChange={onChange}
        loadOptions={loadOptions}
        name="test-select"
        value={[]}
        defaultOptions={options}
        {...props}
      />,
    )
  }

  it("should pass options down to the SelectField", async () => {
    renderSortableSelect()

    const selectInput = document.querySelector(
      ".form-input input[id^='react-select']",
    ) as HTMLElement

    await userEvent.setup().click(selectInput)

    await waitFor(() => {
      const menu = document.querySelector("[class*='-menu']")
      expect(menu).toBeInTheDocument()
    })

    const menu = document.querySelector("[class*='-menu']")
    expect(menu).toBeInTheDocument()
  })

  it("should pass isOptionDisabled down to the SelectField", async () => {
    const isOptionDisabled = jest.fn().mockReturnValue(false)
    renderSortableSelect({ isOptionDisabled })

    const selectInput = document.querySelector(
      ".form-input input[id^='react-select']",
    ) as HTMLElement

    await userEvent.setup().click(selectInput)

    await waitFor(() => {
      const menu = document.querySelector("[class*='-menu']")
      expect(menu).toBeInTheDocument()
    })

    expect(isOptionDisabled).toHaveBeenCalled()
  })

  it("should render sortable items for the current value", async () => {
    const value: SortableItem[] = options.slice(0, 3).map((option) => ({
      id: option.value,
      title: option.label,
    }))

    renderSortableSelect({ value })

    await waitFor(() => {
      value.forEach((item) => {
        expect(screen.getByText(item.title)).toBeInTheDocument()
      })
    })
  })

  it("should allow adding another element", async () => {
    const user = userEvent.setup()

    renderSortableSelect()

    const selectInput = document.querySelector(
      ".form-input input[id^='react-select']",
    ) as HTMLElement

    await user.click(selectInput)
    await user.type(selectInput, newOptions[0].label)

    await waitFor(() => {
      const menu = document.querySelector("[class*='-menu']")
      expect(menu).toBeInTheDocument()
    })

    const menu = document.querySelector("[class*='-menu']")
    if (menu) {
      const matchingOptions = within(menu as HTMLElement).getAllByText(
        newOptions[0].label,
      )
      await user.click(matchingOptions[0])
    }

    if (!SETTINGS.features?.SORTABLE_SELECT_QUICK_ADD) {
      const addButton = screen.getByRole("button", { name: /add/i })
      await user.click(addButton)
    }

    await waitFor(() => {
      expect(onChange).toHaveBeenCalled()
    })
  })

  it("should call onChange on option selection when quick add is enabled", async () => {
    SETTINGS.features = { SORTABLE_SELECT_QUICK_ADD: true }
    const user = userEvent.setup()

    renderSortableSelect()

    const selectInput = document.querySelector(
      ".form-input input[id^='react-select']",
    ) as HTMLElement

    await user.click(selectInput)

    await waitFor(() => {
      const menu = document.querySelector("[class*='-menu']")
      expect(menu).toBeInTheDocument()
    })

    const menu = document.querySelector("[class*='-menu']")
    if (menu) {
      const firstOption = menu.querySelector("[class*='-option']")
      if (firstOption) {
        await user.click(firstOption)
      }
    }

    await waitFor(() => {
      expect(onChange).toHaveBeenCalledWith([options[0].value])
    })

    SETTINGS.features = {}
  })

  it("should let you drag and drop items to reorder", async () => {
    const value: SortableItem[] = options.slice(0, 3).map((option) => ({
      id: option.value,
      title: option.label,
    }))

    renderSortableSelect({ value })

    await screen.findByText(value[0].title)

    const onDragEnd = (global as any).__testOnDragEnd
    expect(onDragEnd).toBeDefined()

    onDragEnd({
      active: { id: value[2].id },
      over: { id: value[0].id },
    })

    expect(onChange).toHaveBeenCalledWith([
      value[2].id,
      value[0].id,
      value[1].id,
    ])
  })

  it("should let you remove items", async () => {
    const user = userEvent.setup()
    const value: SortableItem[] = options.slice(0, 3).map((option) => ({
      id: option.value,
      title: option.label,
    }))

    renderSortableSelect({ value })

    await screen.findByText(value[0].title)

    const deleteButtons = screen.getAllByText("remove_circle_outline")
    await user.click(deleteButtons[0])

    await waitFor(() => {
      expect(onChange).toHaveBeenCalledWith([value[1].id, value[2].id])
    })
  })
})
