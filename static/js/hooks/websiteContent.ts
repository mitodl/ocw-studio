import { useRequest } from "redux-query-react"

import { useWebsite } from "../context/Website"
import { websiteContentDetailRequest } from "../query-configs/websites"
import { useSelector } from "react-redux"
import { getWebsiteContentDetailCursor } from "../selectors/websites"
import { WebsiteContent } from "../types/websites"

/**
 * Hook for fetching and accessing a WebsiteContent object
 * given a uuid. As easy as:
 *
 * ```ts
 * const content = useWebsiteContent(uuid)
 * ```
 *
 * Note that this hook depends on `useWebsite`, so it must be
 * called inside of `WebsiteContext.Provider`.
 */
export function useWebsiteContent(uuid: string): WebsiteContent | null {
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

  return resource
}
