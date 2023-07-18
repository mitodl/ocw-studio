import React, {
  ChangeEvent,
  SyntheticEvent,
  useCallback,
  useState
} from "react"
import SelectField, { Option } from "./SelectField"
import { default as SortableItemComponent } from "../SortableItem"
import SortWrapper from "../SortWrapper"
import { DragEndEvent } from "@dnd-kit/core"
import { arrayMove } from "@dnd-kit/sortable"

export interface SortableItem {
  // the UUID for this item
  id: string
  // title, used to display a sortable entry in the list
  title: string
}

interface Props {
  value: SortableItem[]
  // The onChange function takes an array of item IDs as an argument
  onChange: (update: string[]) => void
  options: Option[]
  defaultOptions?: Option[]
  name: string
  loadOptions: (
    inputValue: string,
    callback: (options: Option[]) => void
  ) => void
  isOptionDisabled?: (option: Option) => boolean
}

export default function SortableSelect(props: Props) {
  const {
    options,
    loadOptions,
    defaultOptions,
    value,
    onChange,
    name,
    isOptionDisabled
  } = props
  /**
   * Callback for adding a new item to the field value in the sortable UI. If
   * there is an item 'focused' in the UI (i.e. the user has selected it in the
   * SelectField) then we add that to the current value and call the change
   * shim.
   */
  const addItem = useCallback(
    (event: ChangeEvent<HTMLSelectElement>) => {
      const content = event.target.value;
      if (content) {
        onChange(value.map(item => item.id).concat(content))
      }
    },
    [onChange, value]
  )

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      const { active, over } = event

      if (over && active.id !== over.id) {
        const valueToUse = value.map(item => item.id)

        const movedArray = arrayMove(
          valueToUse,
          valueToUse.indexOf(active.id),
          valueToUse.indexOf(over.id)
        )

        onChange(movedArray)
      }
    },
    [onChange, value]
  )

  /**
   * For removing an item in the sortable UI
   */
  const deleteItem = useCallback(
    (toDelete: string) => {
      onChange(value.map(item => item.id).filter(item => item !== toDelete))
    },
    [onChange, value]
  )

  const isOptionSelected = useCallback(
    (option) => Boolean(value.find((item) => item.id === option.value)),
    [value]
  )

  return (
    <>
      <SelectField
        name={name}
        onChange={addItem}
        options={options}
        loadOptions={loadOptions}
        defaultOptions={defaultOptions}
        isOptionDisabled={isOptionDisabled}
        isOptionSelected={isOptionSelected}
      />
      <SortWrapper
        handleDragEnd={handleDragEnd}
        items={value.map(item => item.id)}
        generateItemUUID={x => x}
      >
        {value.map(item => (
          <SortableItemComponent
            key={item.id}
            title={item.title}
            id={item.id}
            item={item.id}
            deleteItem={deleteItem}
          />
        ))}
      </SortWrapper>
    </>
  )
}
