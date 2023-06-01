import React, { SyntheticEvent, useCallback, useMemo, useState } from "react"
import { sortedUniqBy, sortBy, times } from "lodash"

import SelectField, { Option } from "./SelectField"

export type Level = {
  label: string
  name: string
}

type OptionsMap = Record<string, Record<string, any> | string[]>

type HierarchicalSelection = Array<string | null>

type Props = {
  name: string
  levels: Level[]
  value: HierarchicalSelection[] | null
  onChange: (event: any) => void
  options_map: OptionsMap // eslint-disable-line camelcase
}

const asOption = (str: string | null) => ({
  label: str ?? "-- empty --",
  value: str ?? ""
})

const describeSelection = (selection: HierarchicalSelection): string =>
  selection.filter(Boolean).join(" - ")

/**
 This function takes field data and the current selection and returns a set of options
 to be displayed in each dropdown.
*/
export const calcOptions = (
  optionsMap: OptionsMap,
  selection: HierarchicalSelection,
  levels: Level[]
): Option[][] => {
  // currentOptionsMap is the piece of optionsMap which is at the level depth being looked at.
  // If falsey, assume there are no options to show.
  let currentOptionsMap: any = optionsMap

  // Iterate through the levels in order to show the right options.
  // When an option is selected at one level, options in deeper levels are filtered on that selection.
  return levels.map((_, levelIdx) => {
    const selectedItem = selection[levelIdx]

    // null indicates an empty selection, and we want to show that as the first option
    let optionValues: Array<string | null> = [null]
    if (!currentOptionsMap) {
      // If the previous select field has no selection, then no select field at a deeper level
      // should have options to select.
    } else if (Array.isArray(currentOptionsMap)) {
      optionValues = optionValues.concat(sortBy(currentOptionsMap))
      // if currentOptionsMap is an array, we are at the deepest level
      currentOptionsMap = null
    } else {
      optionValues = optionValues.concat(sortBy(Object.keys(currentOptionsMap)))
      // move currentOptionsMap one level deeper
      currentOptionsMap = selectedItem ? currentOptionsMap[selectedItem] : null
    }

    return optionValues.map(asOption)
  })
}

export default function HierarchicalSelectField(props: Props): JSX.Element {
  const { options_map: optionsMap, levels, value, onChange, name } = props

  const defaultValue = times(levels.length, () => null)
  const [selection, setSelection] =
    useState<HierarchicalSelection>(defaultValue)

  const setSelectedValueFor = useCallback(
    (levelIdx: number, selected: string) => {
      setSelection(oldSelection =>
        oldSelection.map((selection, idx) =>
          idx < levelIdx ? selection : idx === levelIdx ? selected : null
        )
      )
    },
    [setSelection]
  )

  const handleAdd = useCallback(
    (event: SyntheticEvent<HTMLButtonElement>) => {
      event.preventDefault()

      if (selection[0] === null) {
        // nothing is selected, ignore
        return
      }

      const combinedList = [selection.filter(Boolean), ...(value ?? [])]
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
    },
    [defaultValue, name, setSelection, onChange, selection, value]
  )

  const handleDelete = useCallback(
    (idx: number) => (event: SyntheticEvent<HTMLButtonElement>) => {
      event.preventDefault()

      const valueList = value ?? []
      onChange({
        target: {
          value: valueList.filter((_, _idx) => _idx !== idx),
          name
        }
      })
    },
    [name, onChange, value]
  )

  const options = useMemo(
    () => calcOptions(optionsMap, selection, levels),
    [optionsMap, selection, levels]
  )

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
        <button onClick={handleAdd} className="btn cyan-button add">
          Add
        </button>
      </div>
      <div className="py-2 values">
        {(value ?? []).map((tuple: HierarchicalSelection, idx: number) => (
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
