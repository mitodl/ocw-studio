import React, { useState, useEffect } from "react"
import { useRequest } from "redux-query-react"
import { useSelector } from "react-redux"
import { equals, curry } from "ramda"

import SelectField from "./SelectField"
import { useWebsite } from "../../context/Website"

import { websiteContentListingRequest } from "../../query-configs/websites"
import { WEBSITE_CONTENT_PAGE_SIZE } from "../../constants"
import { getWebsiteContentListingCursor } from "../../selectors/websites"

import { Option } from "./SelectField"
import {
  RelationFilter,
  RelationFilterVariant,
  WebsiteContent
} from "../../types/websites"

interface Props {
  name: string
  collection: string
  display_field: string // eslint-disable-line camelcase
  multiple: boolean
  onChange: (event: Event) => void
  value: any
  filter: RelationFilter
}

const filterContent = curry((filter: RelationFilter, entry: WebsiteContent) => {
  if (!filter) {
    return entry
  }

  if (filter.filter_type === RelationFilterVariant.Equals) {
    return equals(entry[filter.field], filter.value)
  }

  return entry
})

export default function RelationField(props: Props): JSX.Element {
  const {
    collection,
    display_field, // eslint-disable-line camelcase
    name,
    multiple,
    onChange,
    value,
    filter
  } = props

  const [offset, setOffset] = useState(0)
  const [options, setOptions] = useState<Option[]>([])

  const website = useWebsite()

  const listingParams = { name: website.name, type: collection, offset }

  useRequest(websiteContentListingRequest(listingParams, true))

  const websiteContentListingCursor = useSelector(
    getWebsiteContentListingCursor
  )

  const listing = websiteContentListingCursor(listingParams)

  const count = listing?.count ?? 0

  useEffect(() => {
    // check if we need to re-run the request
    //
    // if count is greater than our current offset plus page size (i.e. the
    // number of items which will be fetched in the current request) then we
    // need to bump up offset by WEBSITE_CONTENT_PAGE_SIZE to fetch the next
    // page.
    //
    // this will then change the listingParams object and fire off a new
    // request.
    if (count > offset + WEBSITE_CONTENT_PAGE_SIZE) {
      setOffset(offset => (offset += WEBSITE_CONTENT_PAGE_SIZE))
    }
  }, [offset, setOffset, count])

  useEffect(() => {
    const options: any = (listing?.results ?? [])
      .map((entry: any) => ({
        ...entry,
        ...entry.metadata
      }))
      .filter(filterContent(filter))
      .map((entry: any) => ({
        label: entry[display_field],
        value: entry.text_id
      }))

    setOptions(oldOptions => [...oldOptions, ...options])
  }, [listing, setOptions, display_field, filter]) // eslint-disable-line camelcase

  return (
    <SelectField
      name={name}
      value={value}
      onChange={onChange}
      options={options}
      multiple={multiple}
    />
  )
}
