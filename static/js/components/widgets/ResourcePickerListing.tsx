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
  insertEmbed: (id: string) => void
  setOpen: (open: boolean) => void
  attach: string
  filter: string | null
  filetype: string
}

export default function ResourcePickerListing(
  props: Props
): JSX.Element | null {
  const { insertEmbed, setOpen, attach, filter, filetype } = props
  const website = useWebsite()

  const listingParams: ContentListingParams = useMemo(
    () =>
      Object.assign(
        {
          name:   website.name,
          type:   attach,
          offset: 0
        },
        filetype ? { filetype } : null,
        filter ? { search: filter } : null
      ),
    [website, attach, filter, filetype]
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
      {listing.results.map((item, idx) => (
        <div
          className="resource-item"
          key={`${item.text_id}_${idx}`}
          onClick={(event: SyntheticEvent<HTMLDivElement>) => {
            event.preventDefault()

            insertEmbed(item.text_id)
            setOpen(false)
          }}
        >
          <h4>{item.title}</h4>
        </div>
      ))}
    </div>
  )
}
