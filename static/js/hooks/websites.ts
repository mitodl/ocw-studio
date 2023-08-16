import { useRequest } from "redux-query-react"
import { uniqBy } from "ramda"

import { Additional, Option } from "../components/widgets/SelectField"
import { useWebsite } from "../context/Website"
import {
  websiteContentDetailRequest,
  WebsiteListingResponse
} from "../query-configs/websites"
import { useSelector } from "react-redux"
import { getWebsiteContentDetailCursor } from "../selectors/websites"
import { Website, WebsiteContent } from "../types/websites"
import { useCallback, useEffect, useState } from "react"
import { siteApiListingUrl } from "../lib/urls"
import { debouncedFetch } from "../lib/api/util"
import { QueryState } from "redux-query"
import { LoadOptions } from "react-select-async-paginate"

/**
 * A SelectField Option that is specific to websites.
 */
export interface WebsiteOption extends Option {
  shortId: string
}

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
export function useWebsiteContent(
  uuid: string,
  requestContentContext = false
): [WebsiteContent | null, QueryState] {
  const website = useWebsite()

  const contentParams = {
    name:   website.name,
    textId: uuid
  }

  const [request] = useRequest(
    websiteContentDetailRequest(contentParams, requestContentContext)
  )

  const websiteContentDetailSelector = useSelector(
    getWebsiteContentDetailCursor
  )

  const resource = websiteContentDetailSelector(contentParams)

  return [resource, request]
}

/**
 * Format an array of Website objects into an array of Option
 * objects, which can be passed to a Select field.
 *
 * The `valueField` argument indicates what field on the Website
 * you'd like to use for a user-readable label.
 */
export const formatWebsiteOptions = (
  websites: Website[],
  valueField: string
): WebsiteOption[] =>
  websites.map(website => ({
    label:   website.title,
    shortId: website.short_id,
    value:   website[valueField]
  }))

interface ReturnProps {
  options: WebsiteOption[]
  loadOptions: LoadOptions<
    WebsiteOption,
    WebsiteOption[],
    Additional | undefined
  >
}

/**
 * Hook for fetching websites for use in a select component
 *
 * The hook returns two things, an array of `Option` objects which
 * can be directly used in a `Select` field and a `loadOptions` function
 * which can be used to fetch new options.
 */
export function useWebsiteSelectOptions(
  valueField = "uuid",
  published: boolean | undefined = undefined
): ReturnProps {
  const [options, setOptions] = useState<WebsiteOption[]>([])

  const loadOptions = useCallback(
    async (
      inputValue: string,
      loadedOptions: WebsiteOption[],
      additional?: Additional
    ) => {
      const url = siteApiListingUrl
        .query({ offset: loadedOptions.length })
        .param({ search: inputValue })
        .param(published !== undefined ? { published } : {})
        .toString()

      // using plain fetch rather than redux-query here because this
      // use-case doesn't exactly jibe with redux-query: we need to issue
      // a request programmatically on user input.
      //
      // if we're not operating in callback-mode then we can use a plain fetch
      // instead (which lets us sidestep an issue with debouncedFetch calls
      // running on component mount)
      const response = additional?.callback ?
        await debouncedFetch("website-collection", 300, url, {
          credentials: "include"
        }) :
        await fetch(url, { credentials: "include" })

      if (!response) {
        // this happens if this fetch was ignored in favor of a later fetch
        return {
          hasMore: true, // so one can try again
          options: [] // nothing new
        }
      }
      const json: WebsiteListingResponse = await response.json()
      const { results } = json
      const paginationValues = {
        hasMore: Boolean(json.next)
      }

      const options = formatWebsiteOptions(results, valueField)
      setOptions(current =>
        uniqBy(option => option.value, [...current, ...options])
      )
      if (additional?.callback) {
        additional.callback(options)
      }
      return {
        options,
        ...paginationValues
      }
    },
    [setOptions, valueField, published]
  )

  // on startup we want to fetch options initially so defaultOptions can
  // be set on SelectField components which consume the output from this hook
  useEffect(() => {
    let mounted = true
    if (mounted) {
      loadOptions("", [], {})
    }
    return () => {
      mounted = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return { options, loadOptions }
}
