import wait from "waait"
jest.mock("waait")

import { debouncedFetch, sharedWait } from "./util"

describe("api utility functions", () => {
  it("waits", async () => {
    await Promise.all([
      sharedWait("key", 30),
      sharedWait("key", 30),
      sharedWait("key", 30),
      sharedWait("key2", 30)
    ])
    await sharedWait("key", 30)

    // should only be 3 calls:
    // - the first 3 sharedWait should have started within the 30 ms delay
    // - the fourth has a different key so it should get its own wait
    // - and the fifth is executed after the other sharedWait calls have resolved,
    // so it should start with a clean slate
    expect(wait).toHaveBeenCalledTimes(3)
  })

  it("debounces and fetches", async () => {
    global.fetch = jest.fn()

    await Promise.all([
      debouncedFetch("key", 30, "url1", { credentials: "include" }),
      debouncedFetch("key", 30, "url2", { credentials: "omit" }),
      debouncedFetch("key", 30, "url3", { credentials: "same-origin" }),
      debouncedFetch("key", 30, "url3", { credentials: "omit" })
    ])

    expect(global.fetch).toHaveBeenCalledTimes(1)
    // only the last set of arguments should be passed to fetch
    expect(global.fetch).toHaveBeenCalledWith("url3", {
      credentials: "omit"
    })
  })

  it("resolves the most recent call to fetch result", async () => {
    global.mockFetch.mockResolvedValue("meow")

    const results = await Promise.all([
      debouncedFetch("key", 30, "url1", { credentials: "include" }),
      debouncedFetch("key", 30, "url2", { credentials: "omit" }),
      debouncedFetch("key", 30, "url3", { credentials: "same-origin" }),
      debouncedFetch("key", 30, "url3", { credentials: "omit" })
    ])

    expect(results).toEqual([null, null, null, "meow"])
  })
})
