import { clamp } from "lodash"
import { useEffect, useState } from "react"
import { useHistory, useLocation } from "react-router"
import { useDebouncedEffect } from "./effect"
import { useTextInputState } from "./state"
import { WEBSITE_CONTENT_PAGE_SIZE } from "../constants"

interface URLParamFilterReturnValue<ParamType> {
  searchInput: string
  setSearchInput: React.ChangeEventHandler<HTMLInputElement>
  listingParams: ParamType
}

interface ListingParamsMinimum {
  search?: string | null | undefined
  offset?: number | null | undefined
}

/**
 * Simple, URL-param search support
 *
 * Search text is echoed to the `q` URL parameter.
 */
export function useURLParamFilter<LParams extends ListingParamsMinimum>(
  getListingParams: (search: string) => LParams
): URLParamFilterReturnValue<LParams> {
  const { search } = useLocation()
  const history = useHistory()

  const [listingParams, setListingParams] = useState<LParams>(() =>
    getListingParams(search)
  )

  const [searchInput, setSearchInput] = useTextInputState(
    listingParams.search ?? ""
  )

  /**
   * This debounced effect listens on the search input and, when it is
   * different from the value current set on `listingParams`, will format a new
   * query string (with offset reset to zero) and push that onto the history
   * stack.
   *
   * We are using the URL and the browser's history mechanism as our source of
   * truth for when we are going to re-run the search and whatnot. So in this
   * call we're just concerned with debouncing user input (on the text input)
   * and then basically echoing it up to the URL bar every so often. Below we
   * listen to the `search` param and regenerate `listingParams` when it
   * changes.
   */
  useDebouncedEffect(
    () => {
      const currentSearch = listingParams.search ?? ""
      if (searchInput !== currentSearch) {
        const newParams = new URLSearchParams()
        if (searchInput) {
          newParams.set("q", searchInput)
        }
        const newSearch = newParams.toString()
        history.push(`?${newSearch}`)
      }
    },
    [searchInput, listingParams],
    600
  )

  /**
   * Whenever the search params in the URL change we want to generate a new
   * value for `listingParams`. This will in turn trigger the request to re-run
   * and fetch new results.
   */
  useEffect(() => {
    setListingParams(getListingParams(search))
  }, [search, setListingParams, getListingParams])

  return {
    searchInput,
    setSearchInput,
    listingParams
  }
}

/**
 * The location interface used by react-router
 */
type RLocation = ReturnType<typeof useLocation>

const offsetLocation = (
  location: RLocation,
  count: number,
  increment: number
): RLocation | null => {
  const params = new URLSearchParams(location.search)
  const offset = Number(params.get("offset"))
  if (offset === 0 && increment < 0) return null
  const newOffset = clamp(offset + increment, 0, count)
  if (newOffset >= count) return null
  params.set("offset", String(newOffset))
  return {
    ...location,
    search: params.toString()
  }
}

export const usePagination = (
  count: number,
  pageSize: number = WEBSITE_CONTENT_PAGE_SIZE
): {
  previous: RLocation | null
  next: RLocation | null
} => {
  const location = useLocation()
  const previous = offsetLocation(location, count, -pageSize)
  const next = offsetLocation(location, count, +pageSize)
  return { previous, next }
}
