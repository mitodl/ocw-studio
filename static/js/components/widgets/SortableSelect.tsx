import React, {
  ChangeEvent,
  SyntheticEvent,
  useCallback,
  useState
} from "react"
import SelectField, { Option } from "./SelectField"
import SortableItem from "../SortableItem"
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
  loadOptions: (inputValue: string) => Promise<Option[] | undefined>
  name: string
}

export default function SortableSelect(props: Props) {
  const { options, loadOptions, defaultOptions, value, onChange, name } = props

  const [focusedContent, setFocusedContent] = useState<string | undefined>(
    undefined
  )

  /**
   * Callback for adding a new item to the field value in the sortable UI. If
   * there is an item 'focused' in the UI (i.e. the user has selected it in the
   * SelectField) then we add that to the current value and call the change
   * shim.
   */
  const addFocusedItem = useCallback(
    (event: SyntheticEvent<HTMLButtonElement>) => {
      event.preventDefault()

      if (focusedContent) {
        onChange(value.map(item => item.id).concat(focusedContent))
        setFocusedContent(undefined)
      }
    },
    [focusedContent, setFocusedContent, onChange, value]
  )

  /**
   * This callback is only used for the SelectField that
   * we present as an 'add' interface when this component
   * is displayin the sortable mode.
   */
  const handleAddSortableItem = useCallback(
    (event: ChangeEvent<HTMLSelectElement>) => {
      setFocusedContent(event.target.value)
    },
    [setFocusedContent]
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

  return (
    <>
      <div className="d-flex">
        <SelectField
          name={name}
          value={focusedContent}
          onChange={handleAddSortableItem}
          options={options}
          loadOptions={loadOptions}
          defaultOptions={defaultOptions}
        />
        <button
          className="px-4 ml-3 btn cyan-button"
          disabled={focusedContent === undefined}
          onClick={addFocusedItem}
        >
          Add
        </button>
      </div>
      <SortWrapper
        handleDragEnd={handleDragEnd}
        items={value.map(item => item.id)}
        generateItemUUID={x => x}
      >
        {value.map(item => (
          <SortableItem
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
