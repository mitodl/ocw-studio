import React from "react"
import userEvent from "@testing-library/user-event"
import { render, act } from "@testing-library/react"
import { useHistory, Route } from "react-router"
import { History as RHistory } from "history"
import Router from "./Router"
import Prompt from "./Prompt"
import { assertNotNil } from "../../test_util"

describe("Router", () => {
  /**
   * Setup tests for router.
   *
   * NOTE! The <Router /> component wraps BrowserRouter which uses the HTML5
   * History API. JSDOM, used by jest, does support the History API so we can
   * test it with jest. But Jest does NOT create a new JSDOM instance between
   * tests (only between test files).
   *
   * Consequently, all tests in this file will share a history stack.
   */
  const setup = () => {
    let browserHistory = null as null | RHistory
    const TestComponent = () => {
      const history = useHistory()
      browserHistory = history
      return <Prompt when={true} message="Confirm me!" onBeforeUnload={true} />
    }
    const { getByText, unmount } = render(
      <div>
        <Router>
          <Route path={"*"} component={TestComponent} />
        </Router>
      </div>,
    )
    assertNotNil(browserHistory)
    // ReactStrap's modal seems to error if not explicitly unmounted
    // before the test ends. Unsure why.
    return { getByText, unmount, browserHistory }
  }

  it('Does not navigate if user clicks "Cancel" on prompt', async () => {
    const buttonText = "Cancel"
    const { browserHistory, getByText, unmount } = setup()
    const user = userEvent.setup()

    expect(browserHistory.location.pathname).toBe("/")
    act(() => browserHistory.push("/woof"))

    expect(browserHistory.location.pathname).toBe("/")

    await act(() =>
      user.pointer([
        { target: getByText(buttonText) },
        { keys: "[MouseLeft]" },
      ]),
    )

    expect(browserHistory.location.pathname).toBe("/")

    unmount()
  })

  it('Does navigate if user clicks "Confirm" on prompt', async () => {
    const buttonText = "Confirm"
    const { browserHistory, getByText, unmount } = setup()
    const user = userEvent.setup()

    expect(browserHistory.location.pathname).toBe("/")
    act(() => browserHistory.push("/woof"))

    expect(browserHistory.location.pathname).toBe("/")

    await act(() =>
      user.pointer([
        { target: getByText(buttonText) },
        { keys: "[MouseLeft]" },
      ]),
    )

    expect(browserHistory.location.pathname).toBe("/woof")

    unmount()

    // Go back to '/' at test end since history is shared within this file.
    act(() => browserHistory.push("/"))
    expect(browserHistory.location.pathname).toBe("/")
  })
})
