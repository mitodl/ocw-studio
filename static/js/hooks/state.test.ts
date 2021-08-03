import { renderHook, act } from "@testing-library/react-hooks"

import { useDebouncedState } from "./state"

describe("State Hooks", () => {
  describe("useDebouncedState", () => {
    it("should return the default state", () => {
      const { result } = renderHook(() =>
        useDebouncedState("initialState", 300)
      )
      expect(result.current[0]).toBe("initialState")
    })

    it("should set new state when the debounce period is over", () => {
      const { result } = renderHook(() =>
        useDebouncedState("initialState", 300)
      )

      act(() => result.current[1]("newState"))
      expect(result.current[0]).toBe("initialState")

      act(() => result.current[1].flush())
      expect(result.current[0]).toBe("newState")
    })
  })
})
