import React, { useCallback, ChangeEvent } from "react"
import Select from "react-select"
import AsyncSelect from "react-select/async"
import { is, isNil } from "ramda"

export interface Option {
  label: string
  value: string
}

interface Props {
  name: string
  value: any
  className?: string
  onChange: (event: ChangeEvent<HTMLSelectElement>) => void
  multiple?: boolean
  options: Array<string | Option>
  loadOptions?: (s: string, cb: (options: Option[]) => void) => void
  placeholder?: string
  defaultOptions?: Option[]
}

export default function SelectField(props: Props): JSX.Element {
  const {
    value,
    onChange,
    name,
    options,
    loadOptions,
    defaultOptions,
    placeholder
  } = props
  const multiple = props.multiple ?? false
  const selectOptions = options.map((option: any) =>
    is(String, option) ? { label: option, value: option } : option
  )

  const changeHandler = useCallback(
    (newValue: any) => {
      const eventValue = multiple ?
        newValue.map((option: Option) => option.value) :
        newValue.value
      onChange({ target: { value: eventValue, name } } as ChangeEvent<
        HTMLSelectElement
      >)
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
    selected = isNil(value) ? null : getSelectOption(value)
  }

  return loadOptions ? (
    <AsyncSelect
      className="w-100"
      value={selected}
      isMulti={multiple}
      onChange={changeHandler}
      options={selectOptions}
      loadOptions={loadOptions}
      placeholder={placeholder || null}
      defaultOptions={defaultOptions}
    />
  ) : (
    <Select
      className="w-100"
      value={selected}
      isMulti={multiple}
      onChange={changeHandler}
      options={selectOptions}
      placeholder={placeholder || null}
    />
  )
}
