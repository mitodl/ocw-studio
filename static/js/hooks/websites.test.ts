import { act, renderHook } from "@testing-library/react-hooks"

import { Website } from "../types/websites"
import { makeWebsiteListing } from "../util/factories/websites"
import { formatWebsiteOptions, useWebsiteSelectOptions } from "./websites"
import { debouncedFetch } from "../lib/api/util"
import { siteApiListingUrl } from "../lib/urls"

jest.mock("../lib/api/util", () => ({
  ...jest.requireActual("../lib/api/util"),
  debouncedFetch: jest.fn()
}))

describe("website hooks", () => {
  describe("useWebsiteSelectOptions", () => {
    let websites: Website[]

    beforeEach(() => {
      websites = makeWebsiteListing()
      // @ts-ignore
      debouncedFetch.mockReturnValue({
        json: () => ({ results: websites })
      })
      // @ts-ignore
      global.fetch.mockReturnValue({
        json: () => ({ results: websites })
      })
    })

    afterEach(() => {
      // @ts-ignore
      debouncedFetch.mockReset()
    })

    it("should fetch options on startup by default", async () => {
      const { result, waitForNextUpdate } = renderHook(useWebsiteSelectOptions)
      await act(async () => {
        await waitForNextUpdate()
      })
      expect(global.fetch).toBeCalledWith(
        siteApiListingUrl
          .query({ offset: 0 })
          .param({ search: "" })
          .toString(),
        { credentials: "include" }
      )
      expect(result.current.options).toEqual(
        formatWebsiteOptions(websites, "uuid")
      )
    })

    it("should skip fetching options on startup if argument set", async () => {
      renderHook(() => useWebsiteSelectOptions("uuid", false))
      expect(debouncedFetch).toBeCalledTimes(0)
    })

    //
    ;[true, false].forEach(published => {
      it(`should set published=${String(
        published
      )} if you pass the option`, async () => {
        const { waitForNextUpdate } = renderHook(() =>
          useWebsiteSelectOptions("uuid", true, published)
        )
        await act(async () => {
          await waitForNextUpdate()
        })
        expect(global.fetch).toBeCalledWith(
          siteApiListingUrl
            .query({ offset: 0 })
            .param({ search: "" })
            .param({ published })
            .toString(),
          { credentials: "include" }
        )
      })
    })

    it("should let you issue a debounced request with a search param if you pass a callback", async () => {
      const { result, waitForNextUpdate } = renderHook(useWebsiteSelectOptions)
      const cb = jest.fn()
      await act(async () => {
        await waitForNextUpdate()
        await result.current.loadOptions("search string", cb)
      })
      expect(debouncedFetch).toBeCalledWith(
        "website-collection",
        300,
        siteApiListingUrl
          .query({ offset: 0 })
          .param({ search: "search string" })
          .toString(),
        { credentials: "include" }
      )
      expect(cb).toBeCalledWith(formatWebsiteOptions(websites, "uuid"))
    })
  })
})
