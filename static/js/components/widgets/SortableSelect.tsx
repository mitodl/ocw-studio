import React, {
  ChangeEvent,
  SyntheticEvent,
  useCallback,
  useState
} from "react"
import SelectField, { Additional, Option } from "./SelectField"
import { default as SortableItemComponent } from "../SortableItem"
import SortWrapper from "../SortWrapper"
import { DragEndEvent } from "@dnd-kit/core"
import { arrayMove } from "@dnd-kit/sortable"
import { LoadOptions } from "react-select-async-paginate"
import { isFeatureEnabled } from "../../util/features"

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
  classNamePrefix?: string
  loadOptions: LoadOptions<Option, Option[], Additional | undefined>
  isOptionDisabled?: (option: Option) => boolean
  cacheUniques?: ReadonlyArray<any>
}

export default function SortableSelect(props: Props) {
  const {
    options,
    loadOptions,
    defaultOptions,
    value,
    onChange,
    name,
    classNamePrefix,
    isOptionDisabled,
    cacheUniques
  } = props

  const [focusedContent, setFocusedContent] = useState<string | undefined>(
    undefined
  )

  const quickAdd = isFeatureEnabled("SORTABLE_SELECT_QUICK_ADD")
  const hideSelectedOptions = isFeatureEnabled("SORTABLE_SELECT_HIDE_SELECTED")
  const preserveSearchText = isFeatureEnabled(
    "SORTABLE_SELECT_PRESERVE_SEARCH_TEXT"
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

  const setFocusedContentCB = useCallback(
    (event: ChangeEvent<HTMLSelectElement>) => {
      setFocusedContent(event.target.value)
    },
    [setFocusedContent]
  )

  const addItemOnChange = useCallback(
    (event: ChangeEvent<HTMLSelectElement>) => {
      const content = event.target.value
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
    option => Boolean(value.find(item => item.id === option.value)),
    [value]
  )

  return (
    <>
      <div className="d-flex">
        <SelectField
          name={name}
          value={focusedContent}
          onChange={quickAdd ? addItemOnChange : setFocusedContentCB}
          options={options}
          loadOptions={loadOptions}
          defaultOptions={defaultOptions}
          isOptionDisabled={isOptionDisabled}
          isOptionSelected={hideSelectedOptions ? isOptionSelected : undefined}
          hideSelectedOptions={hideSelectedOptions}
          preserveSearchText={preserveSearchText}
          classNamePrefix={classNamePrefix}
          cacheUniques={cacheUniques}
        />
        {!quickAdd ? (
          <button
            className="px-4 ml-3 btn cyan-button"
            disabled={focusedContent === undefined}
            onClick={addFocusedItem}
          >
            Add
          </button>
        ) : null}
      </div>
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
