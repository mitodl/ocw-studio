import React from "react"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import sinon, { SinonSandbox, SinonStub } from "sinon"
import { LoadOptions } from "react-select-async-paginate"

import SelectField, { Additional, Option } from "./SelectField"

describe("SelectField", () => {
  let sandbox: SinonSandbox,
    onChangeStub: SinonStub,
    name: string,
    options: Array<string | Option>,
    loadOptions: LoadOptions<Option, Option, Additional>,
    classNamePrefix: string,
    min: number,
    max: number

  beforeEach(() => {
    sandbox = sinon.createSandbox()
    onChangeStub = sandbox.stub()
    loadOptions = jest.fn().mockResolvedValue({
      options: [
        { label: "Async One", value: "async-one" },
        { label: "Async Two", value: "async-two" },
      ],
    })
    name = "test-select"
    options = ["one", "two", { label: "Three", value: "3" }]
    classNamePrefix = "select"
    min = 1
    max = 3
  })

  afterEach(() => {
    sandbox.restore()
  })

  const renderSelect = (props: any = {}) => {
    return render(
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
  }

  it("should pass placeholder to Select", async () => {
    renderSelect({
      placeholder: "This place is held!",
    })
    expect(screen.getByText("This place is held!")).toBeInTheDocument()
  })

  it("should render options in menu when clicked", async () => {
    const user = userEvent.setup()
    renderSelect()

    const input = screen.getByRole("textbox")
    await user.click(input)

    await waitFor(() => {
      expect(screen.getByText("one")).toBeInTheDocument()
      expect(screen.getByText("two")).toBeInTheDocument()
      expect(screen.getByText("Three")).toBeInTheDocument()
    })
  })

  it("should only show unselected menu items when hideSelectedOptions is true", async () => {
    const user = userEvent.setup()
    const { container } = renderSelect({
      hideSelectedOptions: true,
      options: [
        { label: "Not selected", value: "not-selected" },
        { label: "Selected", value: "selected" },
      ],
      value: "selected",
    })

    const input = screen.getByRole("textbox")
    await user.click(input)

    await waitFor(() => {
      const menu = container.querySelector(".select__menu")
      expect(menu).toBeInTheDocument()
      expect(menu).toHaveTextContent("Not selected")
      expect(menu).not.toHaveTextContent("Selected")
    })
  })

  it("should use AsyncPaginate if loadOptions is supplied and infinite scroll is enabled", async () => {
    SETTINGS.features.SELECT_FIELD_INFINITE_SCROLL = true
    const user = userEvent.setup()

    renderSelect({
      loadOptions,
      defaultOptions: [{ label: "Default Option", value: "default" }],
    })

    const input = screen.getByRole("textbox")
    await user.click(input)

    await screen.findByText("Default Option")
  })

  it("should use AsyncSelect if loadOptions is supplied and infinite scroll is disabled", async () => {
    SETTINGS.features.SELECT_FIELD_INFINITE_SCROLL = false
    const user = userEvent.setup()

    renderSelect({
      loadOptions,
      defaultOptions: [{ label: "Default Option", value: "default" }],
    })

    const input = screen.getByRole("textbox")
    await user.click(input)

    await screen.findByText("Default Option")
  })

  it("should disable options when isOptionDisabled returns true", async () => {
    const user = userEvent.setup()
    const isOptionDisabled = (option: Option) => option.value === "two"

    const { container } = renderSelect({ isOptionDisabled })

    const input = screen.getByRole("textbox")
    await user.click(input)

    await waitFor(() => {
      const disabledOption = container.querySelector(
        ".select__option--is-disabled",
      )
      expect(disabledOption).toBeInTheDocument()
      expect(disabledOption).toHaveTextContent("two")
    })
  })

  it("should disable options in AsyncPaginate when isOptionDisabled returns true", async () => {
    SETTINGS.features.SELECT_FIELD_INFINITE_SCROLL = true
    const user = userEvent.setup()
    const isOptionDisabled = (option: Option) => option.value === "default"

    const { container } = renderSelect({
      loadOptions,
      defaultOptions: [{ label: "Default Option", value: "default" }],
      isOptionDisabled,
    })

    const input = screen.getByRole("textbox")
    await user.click(input)

    await waitFor(() => {
      const disabledOption = container.querySelector(
        ".select__option--is-disabled",
      )
      expect(disabledOption).toBeInTheDocument()
      expect(disabledOption).toHaveTextContent("Default Option")
    })
  })

  it("should disable options in AsyncSelect when isOptionDisabled returns true", async () => {
    SETTINGS.features.SELECT_FIELD_INFINITE_SCROLL = false
    const user = userEvent.setup()
    const isOptionDisabled = (option: Option) => option.value === "default"

    const { container } = renderSelect({
      loadOptions,
      defaultOptions: [{ label: "Default Option", value: "default" }],
      isOptionDisabled,
    })

    const input = screen.getByRole("textbox")
    await user.click(input)

    await waitFor(() => {
      const disabledOption = container.querySelector(
        ".select__option--is-disabled",
      )
      expect(disabledOption).toBeInTheDocument()
      expect(disabledOption).toHaveTextContent("Default Option")
    })
  })

  it("should preserve search text on menu close and reopen", async () => {
    const user = userEvent.setup()
    renderSelect({ preserveSearchText: true })

    const input = screen.getByRole("textbox")
    await user.click(input)
    await user.type(input, "An")

    await user.keyboard("{Escape}")

    await user.click(input)

    expect(input).toHaveValue("An")
  })

  it("should preserve search text on option selection", async () => {
    const user = userEvent.setup()
    renderSelect({ preserveSearchText: true })

    const input = screen.getByRole("textbox")
    await user.click(input)
    await user.type(input, "on")

    const option = await screen.findByText("one")
    await user.click(option)

    await user.click(input)

    expect(input).toHaveValue("on")
  })

  it("should mark option as selected when isOptionSelected returns true", async () => {
    const user = userEvent.setup()
    const isOptionSelected = (option: Option) => option.value === "two"

    const { container } = renderSelect({ isOptionSelected })

    const input = screen.getByRole("textbox")
    await user.click(input)

    await waitFor(() => {
      const selectedOption = container.querySelector(
        ".select__option--is-selected",
      )
      expect(selectedOption).toBeInTheDocument()
      expect(selectedOption).toHaveTextContent("two")
    })
  })

  describe("not multiple choice", () => {
    it("renders a select widget with initial value", async () => {
      const value = "one"
      renderSelect({ value })
      expect(screen.getByText("one")).toBeInTheDocument()
    })

    it("calls onChange when option is selected", async () => {
      const user = userEvent.setup()
      renderSelect()

      const input = screen.getByRole("textbox")
      await user.click(input)

      const option = await screen.findByText("two")
      await user.click(option)

      sinon.assert.calledWith(onChangeStub, {
        target: { value: "two", name: name },
      })
    })

    it("handles an empty value gracefully", async () => {
      renderSelect({ value: null })
      expect(screen.queryByText("one")).not.toBeInTheDocument()
      expect(screen.queryByText("two")).not.toBeInTheDocument()
    })
  })

  describe("multiple choice", () => {
    it("renders a select widget with initial values", async () => {
      const value = ["one", "3"]
      renderSelect({ value, multiple: true })
      expect(screen.getByText("one")).toBeInTheDocument()
      expect(screen.getByText("Three")).toBeInTheDocument()
    })

    it("calls onChange with array when option is selected", async () => {
      const user = userEvent.setup()
      renderSelect({ value: ["one"], multiple: true })

      const input = screen.getByRole("textbox")
      await user.click(input)

      const option = await screen.findByText("two")
      await user.click(option)

      sinon.assert.calledWith(onChangeStub, {
        target: { value: ["one", "two"], name: name },
      })
    })

    it("handles an empty value gracefully", async () => {
      renderSelect({ value: null, multiple: true })
      expect(screen.queryByText("one")).not.toBeInTheDocument()
    })
  })
})
