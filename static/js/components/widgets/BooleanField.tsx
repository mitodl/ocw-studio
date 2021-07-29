import React from "react"

const radioOptionId = (name: string, bool: boolean): string =>
  `${name}_${String(bool)}`

interface Props {
  name: string
  value: boolean
  onChange: (event: any) => void
}

/**
 * A widget for editing boolean values
 */
export default function BooleanField(props: Props): JSX.Element {
  const { name, value, onChange } = props

  const handleChange = (event: any): void => {
    onChange({
      target: {
        name:  event.target.name,
        value: event.target.value === "true"
      }
    })
  }

  return (
    <div>
      <input
        type="radio"
        id={radioOptionId(name, true)}
        name={name}
        value="true"
        checked={value === true}
        onChange={handleChange}
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
        onChange={handleChange}
      />
      <label className="px-2" htmlFor={radioOptionId(name, false)}>
        False
      </label>
    </div>
  )
}
