import { createPortal } from "react-dom"
import React from "react"
import { useWebsite } from "../../context/Website"
import { useRequest } from "redux-query-react"
import { websiteContentDetailRequest } from "../../query-configs/websites"
import { useSelector } from "react-redux"
import { getWebsiteContentDetailCursor } from "../../selectors/websites"
import { RESOURCE_TYPE_IMAGE } from "../../constants"

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

    if (filetype === RESOURCE_TYPE_IMAGE) {
      const filename = resource.file!.split("/").slice(-1)

      return createPortal(
        <div className="embedded-resource image my-2 d-flex align-items-center">
          <img className="img-fluid m-2" src={resource.file} />
          <div>
            <h3 className="m-2 title">{title}</h3>
            <span className="font-italic mx-2 text-gray resource-info d-block">
              {filename}
            </span>
          </div>
        </div>,
        el
      )
    }

    return createPortal(
      <div className="embedded-resource my-2">
        <h3 className="ml-2 title">{title}</h3>
        <span className="font-italic ml-2 text-gray resource-info">
          Filetype: {filetype}
        </span>
      </div>,
      el
    )
  }
}
