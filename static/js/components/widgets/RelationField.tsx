import React, { useState, useCallback, useEffect } from "react"
import { equals, curry } from "ramda"
import { uniqBy } from "lodash"

import SelectField, { Option } from "./SelectField"
import { debouncedFetch } from "../../lib/api/util"
import { useWebsite } from "../../context/Website"

import {
  RelationFilter,
  RelationFilterVariant,
  WebsiteContent
} from "../../types/websites"
import { SiteFormValue } from "../../types/forms"
import { XOR } from "../../types/util"
import { siteApiContentListingUrl } from "../../lib/urls"
import { PaginatedResponse } from "../../query-configs/utils"

type BaseProps = {
  name: string
  collection?: string | string[]
  display_field: string // eslint-disable-line camelcase
  multiple: boolean
  value: any
  filter?: RelationFilter
  website?: string
  valuesToOmit?: Set<string>
  contentContext: WebsiteContent[] | null
}

/* NOTE: Either setFieldValue or onChange should be passed in, not both.
 * setFieldValue is passed in under normal circumstances when this widget is being used for some field described
 * in the site config.
 * onChange can be passed in when this widget is needed in a different context and the change behavior needs to be
 * customized.
 */
type NormalWidgetProps = BaseProps & {
  setFieldValue: (key: string, value: SiteFormValue) => void
}
type CustomProps = BaseProps & { onChange: (event: any) => void }

const filterContent = curry((filter: RelationFilter, entry: WebsiteContent) => {
  if (!filter) {
    return entry
  }

  if (filter.filter_type === RelationFilterVariant.Equals) {
    return equals(entry[filter.field], filter.value)
  }

  return entry
})

export default function RelationField(
  props: XOR<NormalWidgetProps, CustomProps>
): JSX.Element {
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
    setFieldValue
  } = props

  const formatOptions = useCallback(
    (listing: WebsiteContent[]) =>
      listing.map(entry => ({
        label: entry[display_field],
        value: entry.text_id
      })),
    [display_field] // eslint-disable-line camelcase
  )

  const [options, setOptions] = useState<Option[]>(
    contentContext ? formatOptions(contentContext) : []
  )
  const [defaultOptions, setDefaultOptions] = useState<Option[]>([])

  const contextWebsite = useWebsite()

  // if website: websitename param is set, then we want to use the context
  // website, else we want to use the cursor to fetch the specified website
  const websiteName = props.website ? props.website : contextWebsite.name

  const handleChange = useCallback(
    (event: any) => {
      if (onChange) {
        onChange(event)
      } else if (setFieldValue) {
        const content = event.target.value

        // need to do this because we've renamed the
        // nested field to get validation working
        setFieldValue(name.split(".")[0], {
          website: websiteName,
          content
        })
      }
    },
    [setFieldValue, onChange, name, websiteName]
  )

  const filterContentListing = (results: WebsiteContent[]) => {
    let newContentListing = results.map((entry: any) => ({
      ...entry,
      ...entry.metadata
    }))
    if (filter) {
      newContentListing = newContentListing.filter(filterContent(filter))
    }
    if (valuesToOmit) {
      newContentListing = newContentListing.filter(
        entry => !valuesToOmit.has(entry.text_id) || value === entry.text_id
      )
    }
    return newContentListing
  }

  const fetchOptions = async (
    search: string | null,
    debounce: boolean,
    withTextIds: boolean
  ) => {
    const textIds =
      value && withTextIds ? (Array.isArray(value) ? value : [value]) : []
    const params = collection ? { type: collection } : { page_content: true }
    const url = siteApiContentListingUrl
      .query({
        detailed_list:   true,
        content_context: true,
        ...(search ? { search: search } : {}),
        ...(textIds.length ? { text_id: textIds, limit: textIds.length } : {}),
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
    return formatOptions(filterContentListing(results))
  }

  const loadOptions = async (inputValue: string) => {
    const newOptions = await fetchOptions(inputValue, true, false)
    if (newOptions) {
      setOptions(oldOptions => uniqBy([...oldOptions, ...newOptions], "value"))
    }
    return newOptions
  }

  useEffect(() => {
    // trigger an initial fetch with the text_ids of the value so we can look up the titles for each item
    // then trigger a second fetch to get default options for the user to view when they open the dropdown
    let mounted = true
    const doFetch = async () => {
      const newOptions = contentContext ?
        [] :
        await fetchOptions(null, false, true)
      const defaultOptions = await fetchOptions(null, false, false)

      // Just making typescript happy. newOptions and defaultOptions should always be true here since debounce=false
      if (mounted && newOptions && defaultOptions) {
        setOptions(oldOptions =>
          uniqBy([...oldOptions, ...defaultOptions, ...newOptions], "value")
        )
        setDefaultOptions(() => defaultOptions)
      }
    }
    doFetch()
    return () => {
      mounted = false
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
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
