import React, { useState, useEffect, useMemo, useCallback } from "react"
import { useRequest } from "redux-query-react"
import { useSelector } from "react-redux"
import { equals, curry } from "ramda"
import { uniqBy } from "lodash"

import SelectField from "./SelectField"
import { useWebsite } from "../../context/Website"

import { websiteContentListingRequest } from "../../query-configs/websites"
import { WEBSITE_CONTENT_PAGE_SIZE } from "../../constants"
import {
  getWebsiteContentListingCursor,
  getWebsiteDetailCursor
} from "../../selectors/websites"
import { websiteDetailRequest } from "../../query-configs/websites"

import {
  RelationFilter,
  RelationFilterVariant,
  WebsiteContent
} from "../../types/websites"
import { SiteFormValue } from "../../types/forms"
import { XOR } from "../../types/util"

type BaseProps = {
  name: string
  collection?: string | string[]
  display_field: string // eslint-disable-line camelcase
  multiple: boolean
  value: any
  filter?: RelationFilter
  website?: string
  valuesToOmit?: Set<string>
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
    display_field, // eslint-disable-line camelcase
    name,
    multiple,
    value,
    filter,
    website: websitename,
    valuesToOmit,
    onChange,
    setFieldValue
  } = props

  const [offset, setOffset] = useState(0)
  const [contentListing, setContentListing] = useState<WebsiteContent[]>([])

  const websiteDetailCursor = useSelector(getWebsiteDetailCursor)
  const websiteContentListingCursor = useSelector(
    getWebsiteContentListingCursor
  )

  useRequest(websitename ? websiteDetailRequest(websitename) : null)
  const contextWebsite = useWebsite()

  // if website: websitename param is set, then we want to use the context
  // website, else we want to use the cursor to fetch the specified website
  const website = websitename ?
    websiteDetailCursor(websitename) :
    contextWebsite

  const listingParams = website ?
    {
      name:   website.name,
      offset: offset,
      ...(collection ? { type: collection } : { pageContent: true })
    } :
    null

  useRequest(
    listingParams ? websiteContentListingRequest(listingParams, true) : null
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

  useEffect(() => {
    let newContentListing = (listing?.results ?? []).map((entry: any) => ({
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

    // here we use uniqBy to remove any possible duplicates
    // e.g. from the request having been run once before
    setContentListing(oldContentListing =>
      uniqBy([...oldContentListing, ...newContentListing], "text_id")
    )
  }, [listing, setContentListing, filter, valuesToOmit, value])

  const options = useMemo(
    () =>
      contentListing.map((entry: any) => ({
        label: entry[display_field],
        value: entry.text_id
      })),
    [contentListing, display_field] // eslint-disable-line camelcase
  )

  const handleChange = useCallback(
    (event: any) => {
      if (onChange) {
        onChange(event)
      } else if (setFieldValue) {
        const content = event.target.value

        // need to do this because we've renamed the
        // nested field to get validation working
        setFieldValue(name.split(".")[0], {
          website: website.name,
          content
        })
      }
    },
    [setFieldValue, onChange, name, website]
  )

  return (
    <SelectField
      name={name}
      value={value}
      onChange={handleChange}
      options={options}
      multiple={multiple}
    />
  )
}
