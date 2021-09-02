import React, { useContext } from "react"

import { Website } from "../types/websites"

/**
 * This allows us to set a website context for a whole component
 * tree, starting, for instance, with our SiteContentListing component.
 * This makes it then easy to grab the current Website from anywhere in
 * the component tree.
 *
 * The easiest way to use it is with the `useWebsite` hook defined in
 * this file, like so:
 *
 * ```ts
 * import { useWebsite } from '../context/Website'
 *
 * const website = useWebsite()
 * ```
 **/
const WebsiteContext = React.createContext<Website | null>(null)
export default WebsiteContext

/**
 * A Utility hook for accessing the website context.
 *
 * This ensures that we're only reading from the context in a setting
 * where the component has an ancestor component setting the value.
 *
 * Additionally, this simplifies the typing of the context value. Since
 * we have a nice run-time guard against a null value we can safely type
 * the return value as `Website`, instead of `Website | null`.
 **/
export function useWebsite(): Website {
  const website = useContext(WebsiteContext)
  if (website === null) {
    throw new Error("useWebsite must be within WebsiteContext.Provider")
  }

  return website
}
