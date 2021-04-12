import React, { useCallback } from "react"
import Select from "react-select"
import { is, isNil } from "ramda"

export interface Option {
  label: string
  value: string
}

interface Props {
  name: string
  value: any
  onChange: (event: Event) => void
  multiple?: boolean
  min?: number
  max?: number
  options: Array<string | Option>
}
export default function SelectField(props: Props): JSX.Element {
  const { value, onChange, name, options } = props
  const multiple = Boolean(props.multiple)
  const selectOptions = options.map((option: any) =>
    is(String, option) ? { label: option, value: option } : option
  )

  const changeHandler = useCallback(
    (newValue: any) => {
      const eventValue = multiple ?
        newValue.map((option: Option) => option.value) :
        newValue.value
      // @ts-ignore
      onChange({ target: { value: eventValue, name } })
    },
    [name, multiple]
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

  return (
    <Select
      value={selected}
      isMulti={Boolean(multiple)}
      onChange={changeHandler}
      options={selectOptions}
    />
  )
}
