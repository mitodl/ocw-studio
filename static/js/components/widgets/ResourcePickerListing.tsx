import React, { SyntheticEvent, useMemo } from "react"
import { useRequest } from "redux-query-react"

import { useWebsite } from "../../context/Website"
import { ContentListingParams } from "../../types/websites"
import {
  websiteContentListingRequest,
  WebsiteContentListingResponse
} from "../../query-configs/websites"
import { useSelector } from "react-redux"
import { getWebsiteContentListingCursor } from "../../selectors/websites"

interface Props {
  focusResource: (id: string) => void
  attach: string
  filter: string | null
  resourcetype: string
  focusedResource: string | null
}

export default function ResourcePickerListing(
  props: Props
): JSX.Element | null {
  const { focusResource, focusedResource, attach, filter, resourcetype } = props
  const website = useWebsite()

  const listingParams: ContentListingParams = useMemo(
    () =>
      Object.assign(
        {
          name:   website.name,
          type:   attach,
          offset: 0
        },
        resourcetype ? { resourcetype } : null,
        filter ? { search: filter } : null
      ),
    [website, attach, filter, resourcetype]
  )

  useRequest(websiteContentListingRequest(listingParams, false, false))

  const listing: WebsiteContentListingResponse = useSelector(
    getWebsiteContentListingCursor
  )(listingParams)

  if (!listing) {
    return null
  }

  return (
    <div className="resource-picker-listing">
      {listing.results.map((item, idx) => {
        const className = `resource-item${
          focusedResource && focusedResource === item.text_id ? " focused" : ""
        }`

        return (
          <div
            className={className}
            key={`${item.text_id}_${idx}`}
            onClick={(event: SyntheticEvent<HTMLDivElement>) => {
              event.preventDefault()
              focusResource(item.text_id)
            }}
          >
            <h4>{item.title}</h4>
          </div>
        )
      })}
    </div>
  )
}
