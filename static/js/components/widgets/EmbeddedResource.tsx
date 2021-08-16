import { createPortal } from "react-dom"
import React from "react"
import { useWebsite } from "../../context/Website"
import { useRequest } from "redux-query-react"
import { websiteContentDetailRequest } from "../../query-configs/websites"
import { useSelector } from "react-redux"
import { getWebsiteContentDetailCursor } from "../../selectors/websites"

interface Props {
  uuid: string
  el: HTMLElement
}

/**
 * Display component for resources embedded in the Markdown editor
 *
 * This is for the editor view layer i.e. for providing some UI when
 * a user is working in the Markdown editor. This component has nothing
 * to do with the rendered view of the embedded resource in Markdown
 * and, subsequently, in Hugo templates.
 */
export default function EmbeddedResource(props: Props): JSX.Element | null {
  const { uuid, el } = props

  const website = useWebsite()

  const contentParams = {
    name:   website.name,
    textId: uuid
  }

  useRequest(websiteContentDetailRequest(contentParams, false))

  const websiteContentDetailSelector = useSelector(
    getWebsiteContentDetailCursor
  )

  const resource = websiteContentDetailSelector(contentParams)

  if (!resource) {
    return null
  } else {
    const filetype = resource.metadata?.filetype ?? "..."
    const title = resource.title ?? resource.text_id

    return createPortal(
      <div className="embedded-resource my-2">
        <h3 className="ml-2 title">{title}</h3>
        <span className="font-italic ml-2 text-gray filetype">
          Filetype: {filetype}
        </span>
      </div>,
      el
    )
  }
}
