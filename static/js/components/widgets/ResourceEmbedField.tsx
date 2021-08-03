import React, { useState, useCallback, SyntheticEvent } from "react"
import { useSelector } from "react-redux"
import { useRequest } from "redux-query-react"

import { useWebsite } from "../../context/Website"
import {
  websiteContentListingRequest,
  WebsiteContentListingResponse
} from "../../query-configs/websites"
import { getWebsiteContentListingCursor } from "../../selectors/websites"
import { ContentListingParams } from "../../types/websites"
import { useDebouncedState } from "../../hooks/state"

interface Props {
  insertEmbed: (id: string) => void
  attach: string
}

export default function ResourceEmbedField(props: Props): JSX.Element {
  const { insertEmbed, attach } = props

  // filterInput is to store user input and is updated synchronously
  // so that the UI stays responsive
  const [filterInput, setFilterInput] = useState("")
  // filter, by contrast, is set by the setFilterDebounced function
  // to cut down on extraneous requests. filter is set as a param in
  // the listingParams object below, so updating the value causes the
  // websiteContentListingRequest to be re-run, so we debounce for
  // less silliness!
  const [filter, setFilterDebounced] = useDebouncedState("", 300)

  const onChangeFilter = useCallback(
    (event: SyntheticEvent<HTMLInputElement>) => {
      const newFilter = event.currentTarget.value
      setFilterInput(newFilter)
      setFilterDebounced(newFilter)
    },
    [setFilterDebounced]
  )

  const website = useWebsite()
  const listingParams: ContentListingParams = {
    name:   website.name,
    type:   attach,
    search: filter,
    offset: 0
  }

  useRequest(websiteContentListingRequest(listingParams, false, false))

  const listing: WebsiteContentListingResponse = useSelector(
    getWebsiteContentListingCursor
  )(listingParams)

  return (
    <div className="my-2 resource-embed-widget">
      <label>Resources</label>
      <input
        placeholder="filter"
        type="text"
        onChange={onChangeFilter}
        value={filterInput}
        className="form-control filter-input"
      />
      <div className="resource-list mx-1">
        {listing.results ?
          listing.results.map(item => (
            <div
              key={item.text_id}
              className="m-2 d-flex justify-content-between resource"
              onClick={() => insertEmbed(item.text_id)}
            >
              <h4>{item.title}</h4>
              <span className="material-icons">insert_drive_file</span>
            </div>
          )) :
          null}
      </div>
    </div>
  )
}
