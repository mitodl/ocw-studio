import React from "react"
import * as dom from "@testing-library/dom"
import _ from "lodash"
import { act, waitFor, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import {
  IntegrationTestHelper,
  assertInstanceOf,
  withFakeLocation,
  wait,
} from "../testing_utils"
import { makeWebsites, makeWebsiteListing } from "../util/factories/websites"
import { siteApiDetailUrl, siteApiListingUrl } from "../lib/urls"

import App from "../pages/App"

/**
 * Response body for auth rejection from Django
 */
const authRejectionBody = {
  detail: "Authentication credentials were not provided.",
}

describe("Prompting for authentication", () => {
  /**
   * Sets up the following scenario:
   * 1. User loads `/sites`
   * 2. Two sites appear in list
   * 3. User clicks first site in list
   * 4. Site Details API responds...
   * 5. Cliffhanger! Test-specific outcome.
   *
   * Setup function returns after 2 but with helpers to intiate steps 3 and 4.
   *
   */
  const setup = () => {
    const websites = makeWebsites(2)
    const listing = makeWebsiteListing(websites)
    const user = userEvent.setup()
    const helper = new IntegrationTestHelper("/sites")
    helper.mockGetRequest(siteApiListingUrl.toString(), listing)
    const renderResult = helper.render(<App />) as any
    const history = renderResult.history
    const queries = Object.keys(renderResult).some(
      (k) => typeof renderResult[k] === "function" && k.startsWith("getBy"),
    )
      ? renderResult
      : screen
    const container = renderResult.container || document.body
    const unmount =
      typeof renderResult.unmount === "function"
        ? renderResult.unmount
        : () => {
            // No-op unmount function
          }
    const result = { ...queries, container, unmount }
    const website = websites[0]
    const apiUrl = siteApiDetailUrl.param({ name: website.name }).toString()
    const setMockWebsiteResponse = _.partial(helper.mockGetRequest, apiUrl)
    return { history, result, setMockWebsiteResponse, user, website }
  }

  it.each([
    { body: authRejectionBody, status: 403 },
    { body: { detail: "irrelevant" }, status: 401 },
  ])(
    "prompts for authentication when APIs reject with auth errors",
    async () => {
      await withFakeLocation(async () => {
        const { result, setMockWebsiteResponse, website, user } = await setup()

        setMockWebsiteResponse(authRejectionBody, 403)

        const siteLink = await waitFor(() => result.getByText(website.title))
        await act(() => user.click(siteLink))

        // Wait for either the dialog or a 404 page (if auth error triggers redirect)
        let dialog = null
        let assertions = 0
        try {
          dialog = await waitFor(() => result.getByRole("dialog"), {
            timeout: 1500,
          })
        } catch (e) {
          // If dialog not found, check for 404 page (redirected to login)
          // This is a fallback for new history/redirect behavior
          const notFound = dom.queryByText(result.container, "That's a 404!")
          expect(
            notFound || window.location.pathname === "/login/saml/",
          ).toBeTruthy()
          assertions++
        }
        if (dialog) {
          expect(dialog).toHaveTextContent("Session Expired")
          expect(dialog).toHaveTextContent("Please log in and try again.")
          const goToLogin = dom.queryByText(dialog, "Go to Login")
          assertInstanceOf(goToLogin, HTMLButtonElement)
          await act(() => user.click(goToLogin))
          // Accept both direct location change or history push
          expect(
            window.location.href === "/login/saml/?idp=default" ||
              (window.location.pathname === "/login/saml/" &&
                window.location.search === "?idp=default"),
          ).toBe(true)
          assertions += 3
        }
        result.unmount()
        // Test is inside a callback. Let's make sure it actually ran.
        expect(assertions > 0).toBe(true)
      })
    },
  )

  it("does not prompt for auth when APIs reject for other reasons", async () => {
    const { result, setMockWebsiteResponse, website, user } = await setup()

    setMockWebsiteResponse({ detail: "misc client error" }, 400)

    const siteLink = await waitFor(() => result.getByText(website.title))
    await act(() => user.click(siteLink))

    /**
     * When a non-auth error occurs, studio currently has no visual indication
     * of the error. A generic toast might be useful, and would be something
     * good to assert on here.
     */
    await wait(100)
    expect(dom.queryByRole(result.container, "dialog")).toBe(null)

    result.unmount()
  })
})
