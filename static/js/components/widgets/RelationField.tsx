import React, {
  ChangeEvent,
  useCallback,
  useEffect,
  useState,
  useMemo
} from "react"
import { equals } from "ramda"
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
import { FormError } from "../forms/FormError"
import { FetchStatus } from "../../lib/api/FetchStatus"
import { useWebsiteSelectOptions } from "../../hooks/websites"
import SortableSelect from "./SortableSelect"

// This is how we store the data when dealing with a cross-site relation
// the first string is the content UUID, and the second is the website UUID
type CrossSitePair = [string, string]

/* eslint-disable camelcase */
interface Props {
  name: string
  collection?: string | string[]
  display_field: string
  multiple: boolean
  value: string | string[] | CrossSitePair[]
  filter?: RelationFilter
  website?: string
  valuesToOmit?: Set<string>
  sortable?: boolean
  contentContext: WebsiteContent[] | null
  onChange: (event: any) => void
  cross_site?: boolean
}
/* eslint-enable camelcase */

/**
 * Turn a list of WebsiteContent objects into a list of Options, suitable
 * for use in a SelectField.
 */
const formatContentOptions = (
  listing: WebsiteContent[],
  displayField: string
): Option[] =>
  listing.map(entry => ({
    label: entry[displayField],
    value: entry.text_id
  }))

export default function RelationField(props: Props): JSX.Element {
  const {
    collection,
    contentContext,
    display_field: displayField,
    name,
    multiple,
    value,
    filter,
    valuesToOmit,
    onChange,
    sortable,
    cross_site: crossSite
  } = props

  const [options, setOptions] = useState<Option[]>(
    contentContext ? formatContentOptions(contentContext, displayField) : []
  )
  const [defaultOptions, setDefaultOptions] = useState<Option[]>([])
  const [contentMap, setContentMap] = useState<Map<string, WebsiteContent>>(
    new Map(
      contentContext ?
        contentContext.map(content => [content.text_id, content]) :
        []
    )
  )
  const [fetchStatus, setFetchStatus] = useState<FetchStatus>(FetchStatus.Ok)

  // When we're using the crossSite option we store the value
  // in an array that looks like `[[uuid, website_name]]` (i.e.
  // of type `CrossSitePair[]`
  //
  // Because in a few places we need to operate on `string[]` (i.e.
  // for reordering in the drag-and-drop UI, removing items, etc)
  // we do something like `value.map(entry => entry[0])` to get an array
  // of just content item UUIDs to operate on. Then later we need to
  // 'rehydrate' this back to `CrossSitePair[]`, so we need to keep
  // around some record of the content UUID <-> website name relationship.
  //
  // This `contentToWebsite: Map<string, string>` allows us to do just that.
  // We can 'rehydrate' from `string[]` to `CrossSitePair[]` by doing
  // something like `value.map(uuid => [uuid, contentToWebsite.get(uuid)])`.
  //
  // We can `useEffect` so we can be sure that whenever the `value` prop
  // changes we update the `Map`.
  const [contentToWebsite, setContentToWebsite] = useState<Map<string, string>>(
    new Map()
  )
  useEffect(() => {
    if (crossSite) {
      setContentToWebsite(
        old => new Map([...old.entries(), ...(value as CrossSitePair[])])
      )
    }
  }, [setContentToWebsite, value, crossSite])

  // In order to support the crossSite option we need to be able to fetch
  // websites (to show as options in the select field) and we need to store
  // a currently-selected website.
  const {
    options: websiteOptions,
    loadOptions: loadWebsiteOptions
  } = useWebsiteSelectOptions("name")
  const [focusedWebsite, setFocusedWebsite] = useState<string | null>(null)
  const setFocusedWebsiteCB = useCallback(
    (event: ChangeEvent<HTMLSelectElement>) => {
      setFocusedWebsite(event.target.value)
    },
    [setFocusedWebsite]
  )

  const contextWebsite = useWebsite()

  // if website: websitename param is set, then we want to use the context
  // website, else we want to use the cursor to fetch the specified website
  const websiteName = props.website ? props.website : contextWebsite.name

  const filterContentListing = useCallback(
    (results: WebsiteContent[]) => {
      const valueAsSet = new Set(Array.isArray(value) ? value.flat() : [value])

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
      const name = crossSite && focusedWebsite ? focusedWebsite : websiteName
      const url = siteApiContentListingUrl
        .query({
          detailed_list:   true,
          ...(crossSite ? { published: true } : {}),
          content_context: true,
          ...(search ? { search } : {}),
          ...(filter &&
          filter.filter_type === RelationFilterVariant.Equals &&
          filter.field === "resourcetype" ?
            { resourcetype: filter.value } :
            {}),
          ...params
        })
        .param({
          name
        })
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

      if (results) {
        setContentMap(cur => {
          const newMap = new Map(cur)
          results.forEach(content => {
            newMap.set(content.text_id, content)
          })
          return newMap
        })

        if (crossSite) {
          setContentToWebsite(cur => {
            const update = new Map(cur)
            results.forEach(websiteContent => {
              update.set(websiteContent.text_id, websiteContent.url_path)
            })
            return update
          })
        }
        setFetchStatus(FetchStatus.Ok)
        return formatContentOptions(filterContentListing(results), displayField)
      } else {
        // there was some error fetching the results
        setFetchStatus(FetchStatus.Error)
        return []
      }
    },
    [
      setFetchStatus,
      filterContentListing,
      websiteName,
      displayField,
      collection,
      filter,
      focusedWebsite,
      setContentToWebsite,
      crossSite
    ]
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
    // we re-fetch default options whenever the focused website changes
    // (this is relevant only for the cross_site use-case)
  }, [focusedWebsite]) // eslint-disable-line react-hooks/exhaustive-deps

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
            content: crossSite ?
              (value as string[]).map(id => [id, contentToWebsite.get(id)]) :
              value
          }
        }
      }
      onChange(updatedEvent)
    },
    [onChange, name, crossSite, contentToWebsite, websiteName]
  )

  const handleChange = useCallback(
    (event: ChangeEvent<HTMLSelectElement>) => {
      onChangeShim(event.target.value)
    },
    [onChangeShim]
  )

  const selectedIds = useMemo(
    () =>
      crossSite ?
        (value as CrossSitePair[]).map(pair => pair[0]) :
        multiple ?
          (value as string[]) :
          [value as string],
    [multiple, value, crossSite]
  )

  const isOptionDisabled = useCallback(
    (option: Option) => {
      return selectedIds.includes(option.value)
    },
    [selectedIds]
  )

  return (
    <>
      {crossSite ? (
        <SelectField
          name="Website"
          value={focusedWebsite}
          onChange={setFocusedWebsiteCB}
          options={websiteOptions}
          loadOptions={loadWebsiteOptions}
          placeholder="Pick a website to search within"
          defaultOptions={websiteOptions}
        />
      ) : null}
      {sortable || crossSite ? (
        <SortableSelect
          name={name}
          onChange={onChangeShim}
          options={options}
          loadOptions={loadOptions}
          defaultOptions={defaultOptions}
          isOptionDisabled={isOptionDisabled}
          value={selectedIds.map(id => {
            const content = contentMap.get(id)
            const title = content ? content.title ?? id : id

            return {
              id,
              title
            }
          })}
        />
      ) : (
        <SelectField
          name={name}
          value={value as string | string[]}
          onChange={handleChange}
          options={options}
          loadOptions={loadOptions}
          multiple={multiple}
          defaultOptions={defaultOptions}
        />
      )}
      {fetchStatus === FetchStatus.Error ? (
        <FormError>Unable to fetch entries for this field.</FormError>
      ) : null}
    </>
  )
}
