import { expectTypeOf } from "expect-type"
import { useLocation } from "react-router"

describe("react-router", () => {
  it("knows that useLocation returns location objects", () => {
    /**
     * This test is intended to prevent us from (again) deleting or erroneously
     * upgrading the dependency @types/history@4.7.9
     *  - @types/react-router v5 depends on this as a dependency and won't work
     *    without it; it erroneously declaries ^4.7.11 as the dependency. If
     *    anything above 4.7.9 is used, the types below become "any" because of
     *    a breaking change in @types/history between 4.7.9 and 4.7.11
     *  - We also use history directly in a test, and its version cannot be
     *    upgraded without breaking react-router types.
     *
     * Let's upgrade to react-router 6... its written in typescript so we won't
     * have to futz around with DefinitelyTyped...
     *
     * expectTypeOf is nice in that it will error if the types below turn into
     * "any". It checks for strict type equality, not just assignability.
     */

    /**
     * Don't use real useLocation. React will complain about hook usage outside
     * of components. The mock is good enough for the compile-time assertions
     * we're after.
     */
    const mock: typeof useLocation = jest.fn(() => ({} as any))
    expectTypeOf(mock().pathname).toEqualTypeOf<string>()
    expectTypeOf(mock().search).toEqualTypeOf<string>()
  })
})
