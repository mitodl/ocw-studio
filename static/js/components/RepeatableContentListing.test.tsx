import React from "react"
import { default as useInterval } from "@use-it/interval"
import { screen, waitFor, within, act } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import RepeatableContentListing from "./RepeatableContentListing"
import { GoogleDriveSyncStatuses } from "../constants"
import WebsiteContext from "../context/Website"

import { twoBooleanTestMatrix } from "../test_util"
import {
  siteApiContentListingUrl,
  siteApiDetailUrl,
  siteApiContentSyncGDriveUrl,
  siteContentNewUrl,
  siteContentDetailUrl,
  siteApiContentDetailUrl,
} from "../lib/urls"
import { IntegrationTestHelper } from "../testing_utils"
import {
  makeRepeatableConfigItem,
  makeWebsiteContentListItem,
  makeWebsiteDetail,
} from "../util/factories/websites"

import {
  RepeatableConfigItem,
  Website,
  WebsiteContentListItem,
} from "../types/websites"
import { singular } from "pluralize"

const spyUseInterval = jest.mocked(useInterval)

function mocko() {
  return <div>mock</div>
}

jest.mock("./widgets/MarkdownEditor", () => ({
  __esModule: true,
  default: mocko,
}))
jest.mock("@use-it/interval", () => ({
  __esModule: true,
  default: jest.fn(),
}))

jest.mock("posthog-js", () => ({
  isFeatureEnabled: jest.fn().mockReturnValue(true),
}))

describe("RepeatableContentListing", () => {
  let helper: IntegrationTestHelper,
    website: Website,
    configItem: RepeatableConfigItem,
    contentListingItems: WebsiteContentListItem[]

  beforeEach(() => {
    SETTINGS.deletableContentTypes = []
    SETTINGS.gdrive_enabled = false

    helper = new IntegrationTestHelper()
    website = makeWebsiteDetail()
    configItem = makeRepeatableConfigItem("resource")
    contentListingItems = [
      makeWebsiteContentListItem(),
      makeWebsiteContentListItem(),
    ]
  })

  afterEach(() => {
    spyUseInterval.mockClear()
    jest.useRealTimers()
  })

  const renderListing = async (
    props: { configItem?: RepeatableConfigItem } = {},
    initialSearch = "",
  ) => {
    const item = props.configItem ?? configItem
    const apiResponse = {
      results: contentListingItems,
      count: contentListingItems.length,
      next: null,
      previous: null,
    }

    helper.mockGetRequest(
      siteApiContentListingUrl
        .param({ name: website.name })
        .query({ offset: 0, type: item.name })
        .toString(),
      apiResponse,
    )

    helper.mockGetRequest(
      siteApiContentListingUrl
        .param({ name: website.name })
        .query({ search: "search", offset: 0, type: item.name })
        .toString(),
      apiResponse,
    )

    if (initialSearch) {
      helper = new IntegrationTestHelper(`/?q=${initialSearch}`)
      helper.mockGetRequest(
        siteApiContentListingUrl
          .param({ name: website.name })
          .query({ search: initialSearch, offset: 0, type: item.name })
          .toString(),
        apiResponse,
      )
    }

    const [result, { history }] = helper.render(
      <WebsiteContext.Provider value={website}>
        <RepeatableContentListing configItem={item} />
      </WebsiteContext.Provider>,
    )

    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 2 })).toBeInTheDocument()
    })

    return { result, history }
  }

  test.each(twoBooleanTestMatrix)(
    "showing gdrive links when gdriveis=%p and isResource=%p",
    async (isGdriveEnabled, isResource) => {
      SETTINGS.gdrive_enabled = isGdriveEnabled
      website.gdrive_url = isGdriveEnabled
        ? "https://drive.google.com/test"
        : null
      const item = makeRepeatableConfigItem(isResource ? "resource" : "page")

      await renderListing({ configItem: item })

      const driveLink = document.querySelector("a.view")
      const syncButton = screen.queryByRole("button", { name: /sync/i })
      const addLink = screen.getByRole("link", { name: /add/i })

      expect(!!driveLink).toBe(isGdriveEnabled && isResource)
      expect(!!syncButton).toBe(isGdriveEnabled && isResource)
      expect(addLink).toBeInTheDocument()
    },
  )

  it("Clicking the gdrive sync button should trigger a sync request", async () => {
    const user = userEvent.setup()
    SETTINGS.gdrive_enabled = true
    website.gdrive_url = "https://drive.google.com/test"

    helper.mockPostRequest(
      siteApiContentSyncGDriveUrl.param({ name: website.name }).toString(),
      {},
      200,
    )
    helper.mockGetRequest(
      siteApiDetailUrl
        .param({ name: website.name })
        .query({ only_status: true })
        .toString(),
      { sync_status: "Complete" },
    )

    await renderListing()

    const syncButton = screen.getByRole("button", { name: /sync/i })
    await user.click(syncButton)

    await waitFor(() => {
      expect(helper.handleRequest).toHaveBeenCalledWith(
        siteApiContentSyncGDriveUrl.param({ name: website.name }).toString(),
        "POST",
        expect.anything(),
      )
    })
  })

  test("should filter based on query param", async () => {
    const searchTerm = "search"
    helper = new IntegrationTestHelper(`/?q=${searchTerm}`)

    helper.mockGetRequest(
      siteApiContentListingUrl
        .param({ name: website.name })
        .query({ search: searchTerm, offset: 0, type: configItem.name })
        .toString(),
      {
        results: contentListingItems,
        count: contentListingItems.length,
        next: null,
        previous: null,
      },
    )

    helper.render(
      <WebsiteContext.Provider value={website}>
        <RepeatableContentListing configItem={configItem} />
      </WebsiteContext.Provider>,
    )

    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 2 })).toBeInTheDocument()
    })

    for (const item of contentListingItems) {
      expect(screen.getByText(item.title as string)).toBeInTheDocument()
    }
  })

  test("should let the user filter via text input", async () => {
    jest.useFakeTimers()
    const user = userEvent.setup({ advanceTimers: jest.advanceTimersByTime })

    helper.mockGetRequest(
      siteApiContentListingUrl
        .param({ name: website.name })
        .query({ search: "my-search-string", offset: 0, type: configItem.name })
        .toString(),
      {
        results: contentListingItems,
        count: contentListingItems.length,
        next: null,
        previous: null,
      },
    )

    const { history } = await renderListing()

    const filterInput = screen.getByPlaceholderText(/search/i)
    await user.type(filterInput, "my-search-string")

    act(() => {
      jest.runAllTimers()
    })

    await waitFor(() => {
      expect(history.location.search).toBe("?q=my-search-string")
    })
  })

  test("should show each content item with edit links", async () => {
    await renderListing()

    for (const item of contentListingItems) {
      const link = screen.getByRole("link", {
        name: new RegExp(item.title as string),
      })
      expect(link).toHaveAttribute(
        "href",
        siteContentDetailUrl
          .param({
            name: website.name,
            contentType: configItem.name,
            uuid: item.text_id,
          })
          .toString(),
      )
    }
  })

  test.each([true, false])(
    "should render a link to open the content editor with right label (isSingular=%p)",
    async (isSingular) => {
      let expectedLabel
      if (!isSingular) {
        configItem.label_singular = undefined
        expectedLabel = singular(configItem.label)
      } else {
        configItem.label_singular = expectedLabel = singular(
          configItem.label_singular as string,
        )
      }
      await renderListing()

      expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent(
        configItem.label,
      )
      const link = screen.getByRole("link", { name: /add/i })
      if (configItem.name === "resource") {
        expect(link).toHaveTextContent("Add Video Resource")
      } else {
        expect(link).toHaveTextContent(`Add ${expectedLabel}`)
      }
      expect(link).toHaveAttribute(
        "href",
        siteContentNewUrl
          .param({
            name: website.name,
            contentType: configItem.name,
          })
          .toString(),
      )
    },
  )

  test.each([true, false])(
    "shows the sync status indicator when gdrive enabled=%p",
    async (gdriveEnabled) => {
      SETTINGS.gdrive_enabled = gdriveEnabled
      website.gdrive_url = gdriveEnabled
        ? "https://drive.google.com/test"
        : null
      website.sync_status = gdriveEnabled
        ? GoogleDriveSyncStatuses.SYNC_STATUS_COMPLETE
        : null

      await renderListing()

      const syncStatus = document.querySelector(".sync-status")
      expect(!!syncStatus).toBe(gdriveEnabled)
    },
  )

  it('should display "Add Video Resource" link if configItem is "resource"', async () => {
    configItem = makeRepeatableConfigItem("resource")
    await renderListing()

    const addLink = screen.getByRole("link", { name: /add/i })
    expect(addLink).toHaveTextContent("Add Video Resource")
    expect(addLink).toHaveAttribute(
      "href",
      siteContentNewUrl
        .param({
          name: website.name,
          contentType: configItem.name,
        })
        .toString(),
    )
  })

  test("should have a route for the EditorDrawer component", async () => {
    await renderListing()

    const expectedPaths = [
      siteContentDetailUrl.param({ name: website.name }).pathname,
      siteContentNewUrl.param({ name: website.name }).pathname,
    ]

    expect(expectedPaths[0]).toContain(website.name)
    expect(expectedPaths[1]).toContain(website.name)
  })

  const deletableTestCases = [
    { name: "external resource", configName: "external-resource" },
    { name: "instructor", configName: "instructor" },
    { name: "page", configName: "page" },
  ]
  deletableTestCases.forEach(({ name, configName }) => {
    it(`should delete ${name}`, async () => {
      const user = userEvent.setup()
      SETTINGS.deletableContentTypes = [configName]
      const item = makeRepeatableConfigItem(configName)
      const contentItem = {
        ...makeWebsiteContentListItem(),
        is_deletable: true,
        is_deletable_by_resourcetype: true,
      }
      contentListingItems = [contentItem]

      helper.mockGetRequest(
        siteApiDetailUrl
          .param({ name: website.name })
          .query({ only_status: true })
          .toString(),
        { sync_status: "Complete" },
      )
      helper.mockDeleteRequest(
        siteApiContentDetailUrl
          .param({
            name: website.name,
            textId: contentItem.text_id,
          })
          .toString(),
        {},
      )
      helper.mockGetRequest(
        siteApiContentListingUrl
          .param({ name: website.name })
          .query({ offset: 0, type: item.name })
          .toString(),
        { results: [], count: 0, next: null, previous: null },
      )

      const { result } = await renderListing({ configItem: item })

      const menuButton = screen.getByRole("button", { name: /more_vert/i })
      await user.click(menuButton)

      const deleteButton = await screen.findByRole("button", {
        name: /delete/i,
      })
      await user.click(deleteButton)

      const dialog = await screen.findByRole("dialog")
      expect(dialog).toHaveTextContent(contentItem.title as string)

      const confirmButton = within(dialog)
        .getAllByRole("button")
        .find((btn) => btn.textContent?.toLowerCase().includes("delete"))
      expect(confirmButton).toBeInTheDocument()
      await user.click(confirmButton!)

      await waitFor(() => {
        expect(helper.handleRequest).toHaveBeenCalledWith(
          siteApiContentDetailUrl
            .param({
              name: website.name,
              textId: contentItem.text_id,
            })
            .toString(),
          "DELETE",
          expect.anything(),
        )
      })

      await waitFor(() => {
        expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
      })

      result.unmount()
    })
  })

  it("should not show Delete for referenced content items", async () => {
    const user = userEvent.setup()
    SETTINGS.deletableContentTypes = ["external-resource"]
    const item = makeRepeatableConfigItem("external-resource")
    const contentItem = {
      ...makeWebsiteContentListItem(),
      is_deletable: false,
      is_deletable_by_resourcetype: true,
    }
    contentListingItems = [contentItem]

    const { result } = await renderListing({ configItem: item })

    const menuButton = screen.getByRole("button", { name: /more_vert/i })
    await user.click(menuButton)

    const deleteButton = await screen.findByRole("button", { name: /delete/i })
    await user.click(deleteButton)

    const dialog = await screen.findByRole("dialog")
    const footerButtons = within(dialog).getAllByRole("button")
    const deleteConfirmButton = footerButtons.find(
      (btn) => btn.textContent?.toLowerCase() === "delete",
    )
    expect(deleteConfirmButton).toBeUndefined()

    const cancelButton = footerButtons.find((btn) =>
      btn.textContent?.toLowerCase().includes("cancel"),
    )
    if (cancelButton) {
      await user.click(cancelButton)
    }

    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    })

    result.unmount()
  })

  describe("pagination", () => {
    const setupPaginationTest = async (count: number, initialOffset = 0) => {
      const pageItems = [
        makeWebsiteContentListItem(),
        makeWebsiteContentListItem(),
      ]

      const searchParams = initialOffset > 0 ? `?offset=${initialOffset}` : ""
      helper = new IntegrationTestHelper(
        `/sites/${website.name}/type/resource/${searchParams}`,
      )

      helper.mockGetRequest(
        siteApiContentListingUrl
          .param({ name: website.name })
          .query({ offset: initialOffset, type: configItem.name })
          .toString(),
        {
          count,
          results: pageItems,
          next: initialOffset + 10 < count ? "next-url" : null,
          previous: initialOffset > 0 ? "prev-url" : null,
        },
      )

      const [result, { history }] = helper.render(
        <WebsiteContext.Provider value={website}>
          <RepeatableContentListing configItem={configItem} />
        </WebsiteContext.Provider>,
      )

      await waitFor(() => {
        expect(screen.getByRole("heading", { level: 2 })).toBeInTheDocument()
      })

      return { result, history }
    }

    it('shows only a "Next" button when on first page with more results', async () => {
      await setupPaginationTest(25, 0)

      const pagination = document.querySelector(".pagination")
      expect(pagination).toBeInTheDocument()

      const prevLink = pagination?.querySelector("a.previous")
      const nextLink = pagination?.querySelector("a.next")

      expect(prevLink).not.toBeInTheDocument()
      expect(nextLink).toBeInTheDocument()
    })

    it('shows only a "Previous" button when on last page', async () => {
      await setupPaginationTest(25, 20)

      const pagination = document.querySelector(".pagination")
      expect(pagination).toBeInTheDocument()

      const prevLink = pagination?.querySelector("a.previous")
      const nextLink = pagination?.querySelector("a.next")

      expect(prevLink).toBeInTheDocument()
      expect(nextLink).not.toBeInTheDocument()
    })

    it('shows both "Previous" and "Next" buttons when in the middle', async () => {
      await setupPaginationTest(25, 10)

      const pagination = document.querySelector(".pagination")
      expect(pagination).toBeInTheDocument()

      const prevLink = pagination?.querySelector("a.previous")
      const nextLink = pagination?.querySelector("a.next")

      expect(prevLink).toBeInTheDocument()
      expect(nextLink).toBeInTheDocument()
    })

    it('shows neither "Previous" nor "Next" when all results fit on one page', async () => {
      await setupPaginationTest(5, 0)

      const pagination = document.querySelector(".pagination")
      expect(pagination).toBeInTheDocument()

      const prevLink = pagination?.querySelector("a.previous")
      const nextLink = pagination?.querySelector("a.next")

      expect(prevLink).not.toBeInTheDocument()
      expect(nextLink).not.toBeInTheDocument()
    })
  })

  describe.each([
    {
      status: GoogleDriveSyncStatuses.SYNC_STATUS_PENDING,
      shouldUpdate: true,
    },
    {
      status: GoogleDriveSyncStatuses.SYNC_STATUS_PROCESSING,
      shouldUpdate: true,
    },
    {
      status: GoogleDriveSyncStatuses.SYNC_STATUS_FAILED,
      shouldUpdate: false,
    },
  ])("sync status polling", ({ status, shouldUpdate }) => {
    beforeEach(() => {
      website = {
        ...website,
        sync_status: status,
        synced_on: "2021-01-01",
      }
    })

    it(`${
      shouldUpdate ? "polls" : "doesn't poll"
    } the website sync status when sync_status=${status}`, async () => {
      SETTINGS.gdrive_enabled = true
      website.gdrive_url = null

      helper.mockGetRequest(
        siteApiDetailUrl
          .param({ name: website.name })
          .query({ only_status: true })
          .toString(),
        { sync_status: "Complete" },
      )

      await renderListing()

      expect(spyUseInterval).toHaveBeenCalled()

      if (shouldUpdate) {
        await act(async () => {
          await spyUseInterval.mock.calls[0][0]?.()
        })
        await waitFor(() => {
          expect(helper.handleRequest).toHaveBeenCalledWith(
            siteApiDetailUrl
              .param({ name: website.name })
              .query({ only_status: true })
              .toString(),
            "GET",
            expect.anything(),
          )
        })
      }
    })
  })
})
