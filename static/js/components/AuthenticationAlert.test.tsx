import React from "react"
import * as dom from "@testing-library/dom"
import _ from "lodash"
import { act, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import {
  IntegrationTestHelper,
  assertInstanceOf,
  withFakeLocation,
  wait
} from "../testing_utils"
import { makeWebsites, makeWebsiteListing } from "../util/factories/websites"
import { siteApiDetailUrl, siteApiListingUrl } from "../lib/urls"

import App from "../pages/App"

/**
 * Response body for auth rejection from Django
 */
const authRejectionBody = {
  detail: "Authentication credentials were not provided."
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
    const [result, { history }] = helper.render(<App />)

    const website = websites[0]
    const apiUrl = siteApiDetailUrl.param({ name: website.name }).toString()
    const setMockWebsiteResponse = _.partial(helper.mockGetRequest, apiUrl)

    return { history, result, setMockWebsiteResponse, user, website }
  }

  it.each([
    { body: authRejectionBody, status: 403 },
    { body: { detail: "irrelevant" }, status: 401 }
  ])(
    "prompts for authentication when APIs reject with auth errors",
    async () => {
      const { result, setMockWebsiteResponse, website, user } = await setup()

      setMockWebsiteResponse(authRejectionBody, 403)

      const siteLink = await waitFor(() => result.getByText(website.title))
      await act(() => user.click(siteLink))

      const dialog = await waitFor(() => result.getByRole("dialog"))

      expect(dialog).toHaveTextContent("Session Expired")
      expect(dialog).toHaveTextContent("Please log in and try again.")

      await withFakeLocation(async () => {
        const goToLogin = dom.queryByText(dialog, "Go to Login")
        assertInstanceOf(goToLogin, HTMLButtonElement)
        await act(() => user.click(goToLogin))
        await waitFor(() => {
          expect(window.location.href).toBe("/login/saml/?idp=default")
        })
      })

      result.unmount()
    }
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
