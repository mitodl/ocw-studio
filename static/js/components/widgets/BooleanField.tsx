import React from "react"

const radioOptionId = (name: string, bool: boolean): string =>
  `${name}_${String(bool)}`

interface Props {
  name: string
  value: boolean
  setFieldValue: (key: string, value: File | boolean | null) => void
}

/**
 * A widget for editing boolean values
 */
export default function BooleanField(props: Props): JSX.Element {
  const { name, value, setFieldValue } = props

  return (
    <div>
      <input
        type="radio"
        id={radioOptionId(name, true)}
        name={name}
        value="true"
        checked={value === true}
        onChange={() => {
          setFieldValue(name, true)
        }}
      />
      <label className="px-2" htmlFor={radioOptionId(name, true)}>
        True
      </label>
      <input
        type="radio"
        id={radioOptionId(name, false)}
        name={name}
        value="false"
        checked={value === false}
        onChange={() => {
          setFieldValue(name, false)
        }}
      />
      <label className="px-2" htmlFor={radioOptionId(name, false)}>
        False
      </label>
    </div>
  )
}
