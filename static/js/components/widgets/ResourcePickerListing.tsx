import React, { SyntheticEvent, useMemo } from "react"
import { useRequest } from "redux-query-react"
import { path } from "ramda"
import { useSelector } from "react-redux"

import {
  RESOURCE_TYPE_DOCUMENT,
  RESOURCE_TYPE_IMAGE,
  RESOURCE_TYPE_VIDEO
} from "../../constants"
import { useWebsite } from "../../context/Website"
import { ContentListingParams, WebsiteContent } from "../../types/websites"
import { websiteContentListingRequest } from "../../query-configs/websites"
import {
  getWebsiteContentListingCursor,
  WebsiteContentSelection
} from "../../selectors/websites"

interface Props {
  focusResource: (item: WebsiteContent) => void
  attach: string
  filter: string | null
  resourcetype: string
  focusedResource: WebsiteContent | null
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

  useRequest(websiteContentListingRequest(listingParams, true, false))

  const listing = useSelector(getWebsiteContentListingCursor)(
    listingParams
  ) as WebsiteContentSelection

  if (!listing) {
    return null
  }

  const className =
    resourcetype === RESOURCE_TYPE_DOCUMENT ?
      "resource-picker-listing column-view" :
      "resource-picker-listing"

  return (
    <div className={className}>
      {listing.results.map((item, idx) => {
        const className = `resource-item${
          focusedResource && focusedResource.text_id === item.text_id ?
            " focused" :
            ""
        }`

        let imageSrc: string | undefined

        if (item.metadata) {
          if (item.metadata.resourcetype === RESOURCE_TYPE_IMAGE) {
            imageSrc = path(["file"], item)
          } else if (item.metadata.resourcetype === RESOURCE_TYPE_VIDEO) {
            imageSrc = path(
              ["metadata", "video_files", "video_thumbnail_file"],
              item
            )
          }
        }

        return (
          <div
            className={className}
            key={`${item.text_id}_${idx}`}
            onClick={(event: SyntheticEvent<HTMLDivElement>) => {
              event.preventDefault()
              focusResource(item)
            }}
          >
            {imageSrc ? (
              <div className="img-wrapper">
                <img className="img-fluid w-100" src={imageSrc} />
              </div>
            ) : null}
            <h4>{item.title}</h4>
          </div>
        )
      })}
    </div>
  )
}
