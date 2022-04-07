import React, { useMemo } from "react"
import classNames from "classnames"
import { useRequest } from "redux-query-react"
import { path } from "ramda"
import { useSelector } from "react-redux"

import { ResourceType } from "../../constants"
import { useWebsite } from "../../context/Website"
import { ContentListingParams, WebsiteContent } from "../../types/websites"
import { websiteContentListingRequest } from "../../query-configs/websites"
import {
  getWebsiteContentListingCursor,
  WebsiteContentSelection
} from "../../selectors/websites"
import { formatUpdatedOn } from "../../util/websites"
import { getExtensionName } from "../../util"

interface Props {
  focusResource: (item: WebsiteContent) => void
  filter: string | null
  resourcetype: string | null
  contentType: string
  focusedResource: WebsiteContent | null
  sourceWebsiteName?: string
  singleColumn: boolean
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
    singleColumn
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

  return (
    <div
      className={classNames("resource-picker-listing", {
        "column-view": singleColumn
      })}
    >
      {listing.results.map((item, idx) => {
        const focusItem: React.MouseEventHandler<HTMLDivElement> = event => {
          event.preventDefault()
          focusResource(item)
        }

        return (
          <PickerListItem
            //  text_id itself *should* be unique, since it's a uuid except for sitemetadata.
            key={`${item.text_id}_${idx}`}
            isWholeRow={singleColumn}
            websiteContent={item}
            onClick={focusItem}
            isFocused={item.text_id === focusedResource?.text_id}
          />
        )
      })}
    </div>
  )
}

type ItemProps = {
  isWholeRow: boolean
  isFocused: boolean
  websiteContent: WebsiteContent
  onClick: React.MouseEventHandler<HTMLDivElement>
}
const PickerListItem = (props: ItemProps) => {
  const { websiteContent, isFocused, isWholeRow } = props
  const className = classNames({
    "resource-item": true,
    focused:         isFocused
  })

  let imageSrc: string | undefined, extension: string | undefined
  if (websiteContent.metadata) {
    if (websiteContent.metadata.resourcetype === ResourceType.Image) {
      imageSrc = path(["file"], websiteContent)
    } else if (websiteContent.metadata.resourcetype === ResourceType.Video) {
      imageSrc = path(
        ["metadata", "video_files", "video_thumbnail_file"],
        websiteContent
      )
    } else {
      extension = getExtensionName(websiteContent.file ?? "")
    }
  }
  return (
    <div className={className} onClick={props.onClick}>
      {imageSrc ? (
        <div>
          <img className="img-fluid w-100" src={imageSrc} />
        </div>
      ) : null}
      {isWholeRow ? (
        <h4 className="d-flex justify-content-between align-items-baseline">
          <span>
            {websiteContent.title}
            {extension && <span className="font-size-75"> (.{extension})</span>}
          </span>
          <span className="text-gray font-size-75">
            Updated {formatUpdatedOn(websiteContent)}
          </span>
        </h4>
      ) : (
        <h4>{websiteContent.title}</h4>
      )}
    </div>
  )
}
