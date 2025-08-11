import React from "react"
import userEvent from "@testing-library/user-event"
import { render } from "@testing-library/react"
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
      browserHistory = history as unknown as RHistory
      return (
        <div>
          <button
            onClick={() => {
              history.push("/")
            }}
          >
            home
          </button>
          <button
            onClick={() => {
              history.push("/somewhere")
            }}
          >
            somewhere
          </button>
          <Prompt
            when={true}
            message={"Are you sure you want to leave this page?"}
            onBeforeUnload={false}
          />
        </div>
      )
    }

    const { getByText, unmount } = render(
      <Router>
        <Route path="*">
          <TestComponent />
        </Route>
      </Router>,
    )

    assertNotNil(browserHistory)

    return {
      browserHistory,
      getByText,
      unmount,
    }
  }

  it("Does not navigate if user cancels window.confirm", async () => {
    const confirmSpy = jest.spyOn(window, "confirm").mockReturnValue(false)

    const { browserHistory, getByText, unmount } = setup()
    const user = userEvent.setup()

    expect(browserHistory.location.pathname).toBe("/")

    await user.click(getByText("somewhere"))

    expect(browserHistory.location.pathname).toBe("/")
    expect(confirmSpy).toHaveBeenCalledWith(
      "Are you sure you want to leave this page?",
    )

    confirmSpy.mockRestore()
    unmount()
  })

  it("Does navigate if user confirms window.confirm", async () => {
    const confirmSpy = jest.spyOn(window, "confirm").mockReturnValue(true)

    const { browserHistory, getByText, unmount } = setup()
    const user = userEvent.setup()

    expect(browserHistory.location.pathname).toBe("/")

    await user.click(getByText("somewhere"))

    expect(browserHistory.location.pathname).toBe("/somewhere")
    expect(confirmSpy).toHaveBeenCalledWith(
      "Are you sure you want to leave this page?",
    )

    confirmSpy.mockRestore()
    unmount()
  })
})
