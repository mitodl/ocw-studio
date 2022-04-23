import React from "react"
import { act } from "@testing-library/react"
import IntegrationTest from "../util/integration_test_helper_new"
import * as dtl from "@testing-library/dom"
import userEvent from "@testing-library/user-event"
import {
  assertInstanceOf,
  absoluteUrl,
  flushEventQueue,
  mergeXProd
} from "../test_util"

import Header from "./Header"
import { logoutUrl, siteApiDetailUrl } from "../lib/urls"
import { makeWebsiteDetail } from "../util/factories/websites"
import { PublishStatus } from "../constants"

describe("Header without loaded website", () => {
  it("includes the site logo and mit logo", () => {
    const helper = new IntegrationTest()

    const [result] = helper.render(<Header />)
    const mitLogo = result.getByAltText("MIT")
    const ocwLogo = result.getByAltText("OCW Studio")

    assertInstanceOf(mitLogo, HTMLImageElement)
    assertInstanceOf(ocwLogo, HTMLImageElement)

    expect(mitLogo.src).toBe(absoluteUrl("/static/images/mit-logo.png"))
    expect(ocwLogo.src).toBe(absoluteUrl("/static/images/ocw-studio-logo.png"))
  })

  it("shows the user's name and logout link for logged in users", () => {
    const helper = new IntegrationTest()
    const [result] = helper.render(<Header />)
    const links = result.container.querySelector("div.links")

    assertInstanceOf(links, HTMLElement)

    const username = dtl.getByText(links, "Jane Doe")
    assertInstanceOf(username, HTMLSpanElement)

    const logout = dtl.getByText(links, "Log out")
    assertInstanceOf(logout, HTMLAnchorElement)
    expect(logout.href).toBe(absoluteUrl(logoutUrl.toString()))
  })

  it("does not show username+logout for anonymous users", () => {
    const helper = new IntegrationTest()
    SETTINGS.user = null // SETTINGS is set in our global setup
    const [result] = helper.render(<Header />)
    const links = result.container.querySelector("div.links")
    expect(links).toBe(null)
  })
})

const makeWebsiteWithStatus = (status: PublishStatus, live: boolean) => {
  const statusField = live ? "live_publish_status" : "draft_publish_status"
  const statusDateField = live ?
    "live_publish_status_updated_on" :
    "draft_publish_status_updated_on"
  return makeWebsiteDetail({
    live_publish_status:             PublishStatus.Aborted,
    draft_publish_status:            PublishStatus.Aborted,
    live_publish_status_updated_on:  "2020-01-01",
    draft_publish_status_updated_on: "2020-01-01",
    [statusField]:                   status,
    [statusDateField]:               "2021-01-01"
  })
}

describe("Header with a loaded website", () => {
  it("shows the website title", async () => {
    const helper = new IntegrationTest()
    const website = makeWebsiteDetail()
    const [result] = helper.render(<Header website={website} />)

    const h2 = result.getByText(website.title)

    expect(h2.tagName).toBe("H2")
  })

  const liveCases = [{ isLive: true }, { isLive: false }]
  const statusCases = {
    polling: [
      { status: PublishStatus.NotStarted, expectedText: "Not started" },
      { status: PublishStatus.Pending, expectedText: "In progress..." }
    ],
    noPolling: [
      { status: PublishStatus.Success, expectedText: "Succeeded" },
      { status: PublishStatus.Errored, expectedText: "Failed" },
      { status: PublishStatus.Aborted, expectedText: "Aborted" }
    ]
  }

  it.each(mergeXProd(liveCases, statusCases.noPolling))(
    "does not poll for publishing updates when status=$status",
    async ({ status, isLive }) => {
      jest.useFakeTimers()

      const helper = new IntegrationTest()
      const website = makeWebsiteWithStatus(status, isLive)

      helper.render(<Header website={website} />)

      const pollingInterval = 5000
      jest.advanceTimersByTime(pollingInterval + 100)
      await flushEventQueue(true)

      expect(helper.handleRequest).toHaveBeenCalledTimes(0)
    }
  )

  it.each(mergeXProd(liveCases, statusCases.polling))(
    "does poll for publishing updates when status=$status",
    async ({ status, isLive }) => {
      jest.useFakeTimers()

      const helper = new IntegrationTest()

      const website = makeWebsiteWithStatus(status, isLive)
      const statusUrl = siteApiDetailUrl
        .param({ name: website.name })
        .query({ only_status: true })
        .toString()
      helper.mockGetRequest(statusUrl, website)

      helper.render(<Header website={website} />)

      const pollingInterval = 5000
      jest.advanceTimersByTime(pollingInterval + 100)
      await flushEventQueue(true)

      expect(helper.handleRequest).toHaveBeenCalledTimes(1)
      expect(helper.handleRequest).toHaveBeenCalledWith(statusUrl, "GET", {})
    }
  )

  it.each(
    mergeXProd(liveCases, [...statusCases.noPolling, ...statusCases.polling])
  )(
    'shows text "$expectedText" when status=$status',
    ({ status, expectedText, isLive }) => {
      const helper = new IntegrationTest()
      const website = makeWebsiteWithStatus(status, isLive)

      const [result] = helper.render(<Header website={website} />)
      expect(result.getByText(expectedText)).toBeDefined()
    }
  )

  test("clicking publish opens the publish drawer", async () => {
    const helper = new IntegrationTest()
    const website = makeWebsiteDetail()
    const [result, { history }] = helper.render(<Header website={website} />)
    await flushEventQueue()
    const publishButton = result.getByTitle("Publish")
    assertInstanceOf(publishButton, HTMLButtonElement)
    const user = userEvent.setup()
    await act(() =>
      user.pointer([{ target: publishButton }, { keys: "[MouseLeft]" }])
    )

    result.getByText("Publish your site")
    expect(history.location.search).toBe("?publish=")

    result.unmount()
  })
})
