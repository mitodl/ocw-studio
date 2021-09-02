import React from "react"
import { createPortal } from "react-dom"

import {
  RESOURCE_TYPE_IMAGE,
  RESOURCE_TYPE_VIDEO,
  RESOURCE_TYPE_DOCUMENT,
  RESOURCE_TYPE_OTHER
} from "../../constants"
import { useWebsiteContent } from "../../hooks/websiteContent"

interface Props {
  uuid: string
  el: HTMLElement
}

const filetypeIconMap = {
  [RESOURCE_TYPE_IMAGE]:    "image",
  [RESOURCE_TYPE_VIDEO]:    "movie",
  [RESOURCE_TYPE_DOCUMENT]: "description",
  [RESOURCE_TYPE_OTHER]:    "attachment"
}

/**
 * Display component for linked resources in the Markdown editor
 */
export default function ResourceLink(props: Props): JSX.Element | null {
  const { uuid, el } = props

  const resource = useWebsiteContent(uuid)

  if (!resource) {
    return null
  } else {
    const title = resource.title
    const filetype = resource.metadata?.filetype
    const icon = filetype ?
      filetypeIconMap[filetype as string] :
      filetypeIconMap[RESOURCE_TYPE_OTHER]

    return createPortal(
      <span className="border">
        <i className="material-icons">{icon}</i>
        {title}
      </span>,
      el
    )
  }
}
