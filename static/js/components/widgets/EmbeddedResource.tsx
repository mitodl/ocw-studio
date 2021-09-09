import React from "react"
import { createPortal } from "react-dom"

import { RESOURCE_TYPE_IMAGE, RESOURCE_TYPE_VIDEO } from "../../constants"
import { useWebsiteContent } from "../../hooks/websiteContent"
import { SiteFormValue } from "../../types/forms"

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

  const resource = useWebsiteContent(uuid)

  if (!resource) {
    return null
  } else {
    const filetype = resource.metadata?.filetype ?? "..."
    const title = resource.title ?? resource.text_id

    if (filetype === RESOURCE_TYPE_IMAGE) {
      const filename = (resource.file ?? "").split("/").slice(-1)[0]

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

    if (filetype === RESOURCE_TYPE_VIDEO) {
      const videoMetadata = (resource.metadata?.video_metadata ?? {}) as Record<
        string,
        SiteFormValue
      >

      const youtubeId = (videoMetadata["youtube_id"] as string) ?? ""

      return createPortal(
        <div className="embedded-resource video my-2 d-flex align-items-center">
          <iframe
            className="m-2"
            width="320"
            height="180"
            src={`https://www.youtube-nocookie.com/embed/${youtubeId}`}
            title="YouTube video player"
            frameBorder="0"
            allow="accelerometer; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
          />
          <div>
            <h3 className="m-2 title">{title}</h3>
            <span className="font-italic mx-2 text-gray description resource-info d-block">
              {resource.metadata?.description ?? ""}
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
