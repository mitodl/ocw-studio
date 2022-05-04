import React from "react"
import { screen } from "@testing-library/react"
import {
  IntegrationTestHelper,
  assertInstanceOf,
  absoluteUrl
} from "../../testing_utils"

import App from "../App"

const LOGIN_TEXT = "Login with MIT Touchstone"

describe("Homepage", () => {
  it("does show Touchstone Login when the user is logged out", () => {
    const helper = new IntegrationTestHelper()
    helper.patchInitialReduxState({ user: { user: null } })
    const [result] = helper.render(<App />)
    const link = result.getByText(LOGIN_TEXT)
    assertInstanceOf(link, HTMLAnchorElement)
    expect(link.href).toBe(absoluteUrl("/login/saml/?idp=default"))
  })

  it("does NOT show Touchstone Login is NOT visible if user is already logged in", () => {
    const helper = new IntegrationTestHelper()
    helper.render(<App />)
    const link = screen.queryByText(LOGIN_TEXT)
    expect(link).toBe(null)
  })

  it("sets the document title", () => {
    const helper = new IntegrationTestHelper()
    helper.render(<App />)
    expect(document.title).toBe("OCW Studio")
  })
})
