import { renderHook, waitFor, act } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import React, { PropsWithChildren } from "react"
import { createMemoryHistory } from "history"
import { Router, Route } from "react-router"
import useAppVersionCheck from "./useAppVersionCheck"

const wrapper: React.FC<PropsWithChildren> = ({ children }) => (
  <MemoryRouter>{children}</MemoryRouter>
)

describe("useAppVersionCheck", () => {
  let fetchSpy: jest.SpyInstance
  const originalLocation = window.location
  const reloadMock = jest.fn()

  beforeEach(() => {
    fetchSpy = jest.spyOn(global, "fetch")
    Object.defineProperty(window, "location", {
      value: { ...originalLocation, reload: reloadMock },
      writable: true,
      configurable: true,
    })
  })

  afterEach(() => {
    fetchSpy.mockRestore()
    reloadMock.mockReset()
    Object.defineProperty(window, "location", {
      value: originalLocation,
      writable: true,
      configurable: true,
    })
  })

  it("fetches the hash on mount", async () => {
    fetchSpy.mockResolvedValue({
      ok: true,
      text: () => Promise.resolve("abc123\n"),
    })

    renderHook(() => useAppVersionCheck(), {
      wrapper,
    })

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith("/static/hash.txt", {
        cache: "no-store",
      })
    })
  })

  it("does not reload when the hash has not changed", async () => {
    fetchSpy.mockResolvedValue({
      ok: true,
      text: () => Promise.resolve("abc123\n"),
    })

    renderHook(() => useAppVersionCheck(), {
      wrapper,
    })

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalled()
    })

    expect(reloadMock).not.toHaveBeenCalled()
  })

  it("does not throw when fetch fails", async () => {
    fetchSpy.mockRejectedValue(new Error("network error"))

    renderHook(() => useAppVersionCheck(), {
      wrapper,
    })

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalled()
    })
  })

  it(
    "forces a reload when hash changes between route navigations " +
      "(e.g., stale deletion modal text)",
    async () => {
      let callCount = 0
      fetchSpy.mockImplementation(() => {
        callCount++
        const hash = callCount <= 1 ? "abc123" : "def456"
        return Promise.resolve({
          ok: true,
          text: () => Promise.resolve(hash),
        })
      })

      const history = createMemoryHistory({ initialEntries: ["/sites"] })
      const historyWrapper: React.FC<PropsWithChildren> = ({ children }) => (
        <Router history={history}>
          <Route path="*">{() => <>{children}</>}</Route>
        </Router>
      )

      renderHook(() => useAppVersionCheck(), {
        wrapper: historyWrapper,
      })

      await waitFor(() => {
        expect(fetchSpy).toHaveBeenCalledTimes(1)
      })

      act(() => {
        history.push("/sites/my-course/type/page")
      })

      await waitFor(() => {
        expect(reloadMock).toHaveBeenCalled()
      })
    },
  )
})
