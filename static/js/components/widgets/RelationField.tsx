import React, { useState, useContext } from "react"
import { useRequest } from "redux-query-react"
import { useSelector } from "react-redux"
import { useRouteMatch } from "react-router-dom"

import WebsiteContext from "../../context/Website"
import { websiteContentListingRequest } from "../../query-configs/websites"

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

  const website = useContext(WebsiteContext)

  console.log(website)
  const listingParams: ContentListingParams = {
    name: website.name,
    type: collection,
    offset
  }

  useRequest(websiteContentListingRequest(listingParams))

  return <div>hey!</div>
}
