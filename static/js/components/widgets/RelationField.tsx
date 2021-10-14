import React, {
  useState,
  useCallback,
  useEffect,
  SyntheticEvent,
  ChangeEvent
} from "react"
import { equals, without } from "ramda"
import { uniqBy } from "lodash"

import SelectField, { Option } from "./SelectField"
import { debouncedFetch } from "../../lib/api/util"
import { useWebsite } from "../../context/Website"
import {
  RelationFilter,
  RelationFilterVariant,
  WebsiteContent
} from "../../types/websites"
import { siteApiContentListingUrl } from "../../lib/urls"
import { PaginatedResponse } from "../../query-configs/utils"
import { DragEndEvent } from "@dnd-kit/core"
import { arrayMove } from "@dnd-kit/sortable"
import SortableItem from "../SortableItem"
import SortWrapper from "../SortWrapper"

interface Props {
  name: string
  collection?: string | string[]
  display_field: string // eslint-disable-line camelcase
  multiple: boolean
  value: string | string[]
  filter?: RelationFilter
  website?: string
  valuesToOmit?: Set<string>
  sortable?: boolean
  contentContext: WebsiteContent[] | null
  onChange: (event: any) => void
}

/**
 * Turn a list of WebsiteContent objects into a list of Options, suitable
 * for use in a SelectField.
 */
const formatOptions = (
  listing: WebsiteContent[],
  display_field: string // eslint-disable-line camelcase
): Option[] =>
  listing.map(entry => ({
    label: entry[display_field],
    value: entry.text_id
  }))

export default function RelationField(props: Props): JSX.Element {
  const {
    collection,
    contentContext,
    display_field, // eslint-disable-line camelcase
    name,
    multiple,
    value,
    filter,
    valuesToOmit,
    onChange,
    sortable
  } = props

  const [options, setOptions] = useState<Option[]>(
    contentContext ? formatOptions(contentContext, display_field) : []
  )
  const [defaultOptions, setDefaultOptions] = useState<Option[]>([])
  const [contentMap, setContentMap] = useState<Map<string, WebsiteContent>>(
    new Map()
  )

  const [focusedContent, setFocusedContent] = useState<string | undefined>(
    undefined
  )

  const contextWebsite = useWebsite()

  // if website: websitename param is set, then we want to use the context
  // website, else we want to use the cursor to fetch the specified website
  const websiteName = props.website ? props.website : contextWebsite.name

  const filterContentListing = useCallback(
    (results: WebsiteContent[]) => {
      const valueAsSet = new Set(Array.isArray(value) ? value : [value])

      return results
        .map(entry => ({
          ...entry,
          ...entry.metadata
        }))
        .filter(entry => {
          if (!filter) {
            return true
          }
          switch (filter.filter_type) {
          case RelationFilterVariant.Equals:
            return equals(entry[filter.field], filter.value)
          default:
            return true
          }
        })
        .filter(entry => {
          if (!valuesToOmit) {
            return true
          } else {
            // we want to exclude all content which is in the `valuesToOmit`
            // OR which is already selected (i.e. can be found in the
            // set `valueAsSet`)
            return (
              !valuesToOmit.has(entry.text_id) || valueAsSet.has(entry.text_id)
            )
          }
        })
    },
    [filter, value, valuesToOmit]
  )

  const fetchOptions = useCallback(
    async (search: string | null, debounce: boolean) => {
      const params = collection ? { type: collection } : { page_content: true }
      const url = siteApiContentListingUrl
        .query({
          detailed_list:   true,
          content_context: true,
          ...(search ? { search: search } : {}),
          ...params
        })
        .param({ name: websiteName })
        .toString()

      const response = debounce ?
        await debouncedFetch("relationfield", 300, url, {
          credentials: "include"
        }) :
        await fetch(url, { credentials: "include" })

      if (!response) {
        // duplicate, another later instance of loadOptions will handle this instead
        return
      }
      const json: PaginatedResponse<WebsiteContent> = await response.json()
      const { results } = json
      setContentMap(cur => {
        const newMap = new Map(cur)
        results.forEach(content => {
          newMap.set(content.text_id, content)
        })
        return newMap
      })
      return formatOptions(filterContentListing(results), display_field)
    },
    // eslint-disable-next-line camelcase
    [filterContentListing, websiteName, display_field, collection]
  )

  const loadOptions = useCallback(
    async (inputValue: string) => {
      const newOptions = await fetchOptions(inputValue, true)
      if (newOptions) {
        setOptions(oldOptions =>
          uniqBy([...oldOptions, ...newOptions], "value")
        )
      }
      return newOptions
    },
    [fetchOptions, setOptions]
  )

  useEffect(() => {
    // trigger a fetch to get default options for the user to view when they
    // open the dropdown
    let mounted = true
    const doFetch = async () => {
      const defaultOptions = await fetchOptions(null, false)

      // working around a warning where a setter was used after unmounting
      // defaultOptions should always be true here since fetchOptions will only ever
      // return null if debounce=true
      if (mounted && defaultOptions) {
        setOptions(oldOptions =>
          uniqBy([...oldOptions, ...defaultOptions], "value")
        )
        setDefaultOptions(() => defaultOptions)
      }
    }
    doFetch()
    return () => {
      mounted = false
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  /**
   * A shim which takes a string or array of strings (the value) and then
   * constructs a fake event and passed that to the onChange function. The shim
   * is needed because the onChange function passed in to these components is
   * typically generated automatically by Formik, so we don't have control over
   * it per se.
   */
  const onChangeShim = useCallback(
    (value: string | string[]) => {
      // When we run renameNestedFields we add a '.content' suffix to the name
      // of the field for RelationField because the data structure looks like
      // this: { content, website } where 'content' is either a string or a
      // list of strings.  Validation by yup is easier to work with when the
      // field name ends with .content because formik validates the value of
      // 'content' instead of '{ content, website }'.  But while that's easier
      // for validation, we still need to send the whole object.  So we need to
      // remove that .content suffix and also add back 'website' when onChange
      // is called.
      const updatedEvent = {
        target: {
          name:  name.replace(/\.content$/, ""),
          value: {
            website: websiteName,
            content: value
          }
        }
      }
      onChange(updatedEvent)
    },
    [onChange, name, websiteName]
  )

  const handleChange = useCallback(
    (event: ChangeEvent<HTMLSelectElement>) => {
      onChangeShim(event.target.value)
    },
    [onChangeShim]
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
        onChangeShim(
          arrayMove(
            value as string[],
            value.indexOf(active.id),
            value.indexOf(over.id)
          )
        )
      }
    },
    [onChangeShim, value]
  )

  /**
   * For removing an item in the sortable UI
   */
  const deleteItem = useCallback(
    (item: string) => {
      onChangeShim(without([item], value as string[]))
    },
    [onChangeShim, value]
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
        onChangeShim(value.concat(focusedContent))
        setFocusedContent(undefined)
      }
    },
    [focusedContent, setFocusedContent, onChangeShim, value]
  )

  return sortable && multiple ? (
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
        items={(value as string[]) ?? []}
        generateItemUUID={x => x}
      >
        {((value as string[]) ?? []).map(textId => {
          const content = contentMap.get(textId)

          return (
            <SortableItem
              key={textId}
              title={content ? (content.title as string) : textId}
              id={textId}
              item={textId}
              deleteItem={deleteItem}
            />
          )
        })}
      </SortWrapper>
    </>
  ) : (
    <SelectField
      name={name}
      value={value}
      onChange={handleChange}
      options={options}
      loadOptions={loadOptions}
      multiple={multiple}
      defaultOptions={defaultOptions}
    />
  )
}
