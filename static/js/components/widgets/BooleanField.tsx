import React from "react"
import { AdditionalLabelsFieldProp } from "../../types/websites"

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
export default function BooleanField(
  props: Props & AdditionalLabelsFieldProp,
): JSX.Element {
  const {
    name,
    value,
    additional_labels: additionalLabels = {},
    onChange,
  } = props

  const handleChange = (event: any): void => {
    onChange({
      target: {
        name: event.target.name,
        value: event.target.value === "true",
      },
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
        {additionalLabels.true_label ?? "True"}
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
        {additionalLabels.false_label ?? "False"}
      </label>
    </div>
  )
}
