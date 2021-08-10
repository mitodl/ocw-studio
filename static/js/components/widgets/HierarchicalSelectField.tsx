import React, { SyntheticEvent, useState } from "react"
import { sortedUniqBy, sortBy, times } from "lodash"

import SelectField, { Option } from "./SelectField"

type Level = {
  label: string
  name: string
}
type OptionsMap = Record<string, Record<string, any> | string[]>
type HierarchicalSelection = Array<string | null>
type Props = {
  name: string
  label: string
  label_singular?: string // eslint-disable-line camelcase
  levels: Level[] // eslint-disable-line camelcase
  value: HierarchicalSelection[] | null
  onChange: (event: any) => void
  options_map: OptionsMap // eslint-disable-line camelcase
}

const asOption = (str: string | null) => ({
  label: str ?? "-- empty --",
  value: str ?? ""
})

export const describeSelection = (selection: HierarchicalSelection): string =>
  selection.filter(Boolean).join(" - ")

export const calcOptions = (
  optionsMap: OptionsMap,
  selection: HierarchicalSelection,
  levels: Level[]
): Option[][] => {
  let previousSelected = true
  let currentOptionsMap: any = optionsMap

  return levels.map((_, levelIdx) => {
    const selectedItem = selection[levelIdx]
    if (!previousSelected) {
      return [null].map(asOption)
    }

    if (!selectedItem) {
      previousSelected = false
    }

    let optionValues: Array<string | null>
    if (Array.isArray(currentOptionsMap)) {
      optionValues = [null, ...sortBy(currentOptionsMap)]
      currentOptionsMap = null
    } else {
      const keys = Object.keys(currentOptionsMap)
      // @ts-ignore
      optionValues = [null, ...sortBy(keys)]
      currentOptionsMap = selectedItem ? currentOptionsMap[selectedItem] : null
    }
    return optionValues.map(asOption)
  })
}

export default function HierarchicalSelectField(props: Props): JSX.Element {
  const { options_map: optionsMap, levels, value, onChange, name } = props

  const labelSingular = props.label_singular ?? props.label
  const valueList = value ?? []

  const defaultValue = times(levels.length, () => null)
  const [selection, setSelection] = useState<HierarchicalSelection>(
    defaultValue
  )

  const setSelectedValueFor = (levelIdx: number, selected: string) => {
    setSelection(oldSelection =>
      oldSelection.map((selection, idx) =>
        idx < levelIdx ? selection : idx === levelIdx ? selected : null
      )
    )
  }

  const handleAdd = (event: SyntheticEvent<HTMLButtonElement>) => {
    event.preventDefault()

    if (selection[0] === null) {
      // nothing is selected, ignore
      return
    }

    const combinedList = [selection, ...valueList]
    onChange({
      target: {
        value: sortedUniqBy(
          sortBy(combinedList, describeSelection),
          describeSelection
        ),
        name
      }
    })
    setSelection(defaultValue)
  }

  const handleDelete = (idx: number) => (
    event: SyntheticEvent<HTMLButtonElement>
  ) => {
    event.preventDefault()

    onChange({
      target: {
        value: valueList.filter((_, _idx) => _idx !== idx),
        name
      }
    })
  }

  const options = calcOptions(optionsMap, selection, levels)

  return (
    <div className="hierarchical-select">
      <div className="d-flex flex-direction-row align-items-center py-2">
        {levels.map((level, levelIdx) => (
          <div key={level.name} className="pr-4 w-100">
            <SelectField
              name={level.name}
              value={selection[levelIdx]}
              onChange={(event: any) => {
                setSelectedValueFor(levelIdx, event.target.value)
              }}
              options={options[levelIdx]}
              placeholder={level.label}
            />
          </div>
        ))}
        <button onClick={handleAdd} className="btn blue-button">
          Add {labelSingular}
        </button>
      </div>
      <div className="py-2">
        {valueList.map((tuple: HierarchicalSelection, idx: number) => (
          <div
            key={idx}
            className="d-flex flex-direction-row align-items-center py-1"
          >
            {describeSelection(tuple)}
            <button
              className="material-icons item-action-button"
              onClick={handleDelete(idx)}
            >
              delete
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
