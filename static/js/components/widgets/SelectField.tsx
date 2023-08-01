import React, { useCallback, ChangeEvent, useState } from "react"
import Select from "react-select"
import { isNil } from "ramda"
import { AsyncPaginate, LoadOptions } from "react-select-async-paginate"
import AsyncSelect from "react-select/async"
import { isFeatureEnabled } from "../../util/features"

export interface Option {
  label: string
  value: string
}

export interface Additional {
  callback?: (options: Option[]) => void
}

interface Props {
  name: string
  classNamePrefix?: string
  value?: null | undefined | string | string[]
  onChange: (event: ChangeEvent<HTMLSelectElement>) => void
  multiple?: boolean
  options: Array<string | Option>
  loadOptions?: LoadOptions<Option, Option[], Additional | undefined>
  placeholder?: string
  defaultOptions?: Option[]
  cacheUniques?: ReadonlyArray<any>
  hideSelectedOptions?: boolean
  isOptionDisabled?: (option: Option) => boolean
  isOptionSelected?: (option: Option) => boolean
}

export default function SelectField(props: Props): JSX.Element {
  const {
    value,
    onChange,
    name,
    classNamePrefix,
    options,
    loadOptions,
    defaultOptions,
    placeholder: initialPlaceholder,
    isOptionDisabled,
    isOptionSelected,
    hideSelectedOptions,
    cacheUniques
  } = props
  const [searchText, setSearchText] = useState("")
  const [placeholder, setPlaceholder] = useState("")

  const preserveSearchText = isFeatureEnabled(
    "SELECT_FIELD_PRESERVE_SEARCH_TEXT"
  )
  const infiniteScroll = isFeatureEnabled("SELECT_FIELD_INFINITE_SCROLL")

  const multiple = props.multiple ?? false
  const selectOptions = options.map(option =>
    typeof option === "string" ? { label: option, value: option } : option
  )

  const changeHandler = useCallback(
    (newValue: any) => {
      const eventValue = multiple ?
        newValue.map((option: Option) => option.value) :
        newValue.value
      onChange({
        target: { value: eventValue, name }
      } as ChangeEvent<HTMLSelectElement>)
    },
    [name, multiple, onChange]
  )

  /**
   * Get or create a select-field Option with the specified value,
   * so it will appear as a selected value even if there is no available
   * select option for it.
   **/
  const getSelectOption = (value: string) => {
    const selectOption = selectOptions.filter(
      option => option.value === value
    )[0]
    return selectOption || { label: value, value: value }
  }

  let selected
  if (multiple) {
    if (!Array.isArray(value)) {
      selected = []
    } else {
      selected = value.map(option => getSelectOption(option))
    }
  } else {
    if (Array.isArray(value)) {
      throw new Error("Array values should specify multiple=true")
    }
    selected = isNil(value) ? null : getSelectOption(value)
  }

  const handleInputChanged = useCallback(
    (input, reason) => {
      if (reason.action === "input-blur") {
        return
      }
      setSearchText(input)
    },
    [setSearchText]
  )

  const handleMenuClosed = useCallback(
    () => setPlaceholder(searchText),
    [setPlaceholder, searchText]
  )

  const handleMenuOpen = useCallback(
    () => setSearchText(placeholder ?? ""),
    [setSearchText, placeholder]
  )

  // For AsyncSelect
  const loadOptionsShim = useCallback(
    async (inputValue: string, cb: (options: Option[]) => void) => {
      if (loadOptions) {
        const result = await loadOptions(inputValue, [], { callback: cb })
        return result?.options ?? []
      }
    },
    [loadOptions]
  )

  const commonSelectOptions = {
    className:         "w-100 form-input",
    classNamePrefix,
    value:             selected,
    isMulti:           multiple,
    options:           selectOptions,
    placeholder:       placeholder || initialPlaceholder || null,
    blurInputOnSelect: preserveSearchText ? true : undefined,
    hideSelectedOptions,
    onChange:          changeHandler,
    inputValue:        preserveSearchText ? searchText : undefined,
    onInputChange:     preserveSearchText ? handleInputChanged : undefined,
    onMenuClose:       preserveSearchText ? handleMenuClosed : undefined,
    onMenuOpen:        preserveSearchText ? handleMenuOpen : undefined,
    isOptionDisabled,
    isOptionSelected,
    styles:            {
      control: (base: any) => ({
        ...base,
        border:    0,
        boxShadow: "none"
      })
    }
  }

  return loadOptions ? (
    infiniteScroll ? (
      <AsyncPaginate
        {...commonSelectOptions}
        loadOptions={loadOptions}
        defaultOptions={defaultOptions}
        cacheUniqs={cacheUniques}
      />
    ) : (
      <AsyncSelect
        {...commonSelectOptions}
        loadOptions={loadOptionsShim}
        defaultOptions={defaultOptions}
      />
    )
  ) : (
    <Select {...commonSelectOptions} />
  )
}
