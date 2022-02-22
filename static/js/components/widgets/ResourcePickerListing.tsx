import React, { SyntheticEvent, useMemo } from "react"
import { useRequest } from "redux-query-react"
import { path } from "ramda"
import { useSelector } from "react-redux"

import {
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
  filter: string | null
  resourcetype: string | null
  contentType: string
  focusedResource: WebsiteContent | null
  sourceWebsiteName?: string
  thumbnails: boolean
}

export default function ResourcePickerListing(
  props: Props
): JSX.Element | null {
  const {
    focusResource,
    focusedResource,
    filter,
    resourcetype,
    contentType,
    sourceWebsiteName,
    thumbnails
  } = props
  const website = useWebsite()

  const listingParams: ContentListingParams = useMemo(
    () =>
      Object.assign(
        {
          name:   sourceWebsiteName ?? website.name,
          type:   contentType,
          offset: 0
        },
        resourcetype ? { resourcetype } : null,
        filter ? { search: filter } : null
      ),
    [website, filter, resourcetype, contentType, sourceWebsiteName]
  )

  useRequest(websiteContentListingRequest(listingParams, true, false))

  const listing = useSelector(getWebsiteContentListingCursor)(
    listingParams
  ) as WebsiteContentSelection

  if (!listing) {
    return null
  }

  const className = thumbnails ?
    "resource-picker-listing" :
    "resource-picker-listing column-view"

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
