import { act, renderHook } from "@testing-library/react-hooks"

import { Website } from "../types/websites"
import { makeWebsites } from "../util/factories/websites"
import { formatWebsiteOptions, useWebsiteSelectOptions } from "./websites"
import * as apiUtils from "../lib/api/util"
import { siteApiListingUrl } from "../lib/urls"

jest.mock("../lib/api/util", () => ({
  ...jest.requireActual("../lib/api/util"),
  debouncedFetch: jest.fn()
}))
const debouncedFetch = jest.mocked(apiUtils.debouncedFetch)

describe("website hooks", () => {
  describe("useWebsiteSelectOptions", () => {
    let websites: Website[]

    beforeEach(() => {
      websites = makeWebsites()

      // @ts-expect-error Not mocking all the properties on Response
      debouncedFetch.mockResolvedValue({
        json: async () => ({ results: websites })
      })
      global.mockFetch.mockReturnValue({
        json: () => ({ results: websites })
      })
    })

    afterEach(() => {
      debouncedFetch.mockReset()
    })

    it("should fetch options on startup by default", async () => {
      const { result, waitForNextUpdate } = renderHook(useWebsiteSelectOptions)
      await act(async () => {
        await waitForNextUpdate()
      })
      expect(global.fetch).toHaveBeenCalledWith(
        siteApiListingUrl
          .query({ offset: 0 })
          .param({ search: "" })
          .toString(),
        { credentials: "include" }
      )
      expect(result.current.options).toEqual(
        formatWebsiteOptions(websites, "title", "uuid")
      )
    })

    //
    ;[true, false].forEach(published => {
      it(`should set published=${String(
        published
      )} if you pass the option`, async () => {
        const { waitForNextUpdate } = renderHook(() =>
          useWebsiteSelectOptions("title", "uuid", published)
        )
        await act(async () => {
          await waitForNextUpdate()
        })
        expect(global.fetch).toHaveBeenCalledWith(
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
      expect(debouncedFetch).toHaveBeenCalledWith(
        "website-collection",
        300,
        siteApiListingUrl
          .query({ offset: 0 })
          .param({ search: "search string" })
          .toString(),
        { credentials: "include" }
      )
      expect(cb).toBeCalledWith(formatWebsiteOptions(websites, "title", "uuid"))
    })
  })
})
