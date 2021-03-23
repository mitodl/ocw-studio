import React from "react"
import Select from "react-select"
import { isNil } from "ramda"

interface Option {
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
  options: string[]
}
export default function SelectField(props: Props): JSX.Element {
  const { value, onChange, name, options } = props
  const multiple = Boolean(props.multiple)

  const changeHandler = (newValue: any) => {
    const eventValue = multiple ?
      newValue.map((option: Option) => option.value) :
      newValue.value
    // @ts-ignore
    onChange({ target: { value: eventValue, name } })
  }

  let selected
  if (multiple) {
    if (!Array.isArray(value)) {
      selected = []
    } else {
      selected = value.map(option => ({ label: option, value: option }))
    }
  } else {
    selected = isNil(value) ? null : { label: value, value: value }
  }

  return (
    <Select
      value={selected}
      isMulti={Boolean(multiple)}
      onChange={changeHandler}
      // @ts-ignore
      options={options.map(option => ({ label: option, value: option }))}
    />
  )
}
