import React, { useState, useContext, useEffect, useMemo } from "react"
import Select from "react-select"
import { useRequest } from "redux-query-react"
import { useSelector } from "react-redux"

import SelectField from './SelectField'
import WebsiteContext from "../../context/Website"

import { websiteContentListingRequest } from "../../query-configs/websites"
import { WEBSITE_CONTENT_PAGE_SIZE } from "../../constants"
import { getWebsiteContentListingCursor } from "../../selectors/websites"

import { Option } from './SelectField'

interface Props {
  name: string
  collection: string
  display_field: string
  max: number
  min: number
  multiple: boolean
  onChange: (event: Event) => void
  value: any
}

export default function RelationField(props: Props): JSX.Element {
  const { collection, display_field, name,  multiple, onChange, value } = props

  console.log(props);

  const [offset, setOffset] = useState(0)

  // technically the Website in WebsiteContext can be null, but in the
  // content where this component is mounted it never should be in practice.
  const website = useContext(WebsiteContext)

  const listingParams = website ? { name: website.name, type: collection, offset } : null

  useRequest(listingParams ? websiteContentListingRequest(listingParams) : null)

  const websiteContentListingCursor = useSelector(
    getWebsiteContentListingCursor
  )

  const listing = listingParams ?
    websiteContentListingCursor(listingParams) :
    null
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

  console.log(listing);

  const options: Option[] = useMemo(() => {
    const options = (listing?.results ?? []).map((entry: any) => ({
      label: entry[display_field],
      value: entry.text_id
    }))

    return options
  }, [listing])


  return <SelectField
    name={name}
    value={value}
    onChange={onChange}
    options={options}
    multiple={multiple}
  />
}

