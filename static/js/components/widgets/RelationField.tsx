import React, { useState, useContext, useEffect } from "react"
import { useRequest } from "redux-query-react"
import { useSelector } from "react-redux"

import WebsiteContext from "../../context/Website"
import { websiteContentListingRequest } from "../../query-configs/websites"
import { WEBSITE_CONTENT_PAGE_SIZE } from "../../constants"
import { getWebsiteContentListingCursor } from "../../selectors/websites"

import { ContentListingParams } from "../../types/websites"

interface Props {
  collection: string
  display_field: string
  max: number
  min: number
  multiple: boolean
  search_fields: string[]
}

export default function RelationField(props: Props): JSX.Element {
  const { collection, display_field, max, min, multiple, search_fields } = props

  const [offset, setOffset] = useState(0)

  const { name } = useContext(WebsiteContext) ?? {}

  const listingParams = name ? { name, type: collection, offset } : null

  useRequest(listingParams ? websiteContentListingRequest(listingParams) : null)

  const websiteContentListingCursor = useSelector(
    getWebsiteContentListingCursor
  )

  const listing = listingParams ?
    websiteContentListingCursor(listingParams) :
    null
  const count = listing?.count ?? 0

  useEffect(() => {
    console.log('effecting');
    console.log(count);
    console.log(offset);


    if (count - (offset + WEBSITE_CONTENT_PAGE_SIZE) > 0) {
      console.log('bumping offset');
      setOffset(offset => (offset += WEBSITE_CONTENT_PAGE_SIZE))
    }
  }, [offset, setOffset, count])

  return <div>hey!</div>
}
