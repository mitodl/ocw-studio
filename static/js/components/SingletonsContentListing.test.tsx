import React from "react"
import { screen, waitFor, act } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import SingletonsContentListing from "./SingletonsContentListing"
import WebsiteContext from "../context/Website"

import { siteApiContentDetailUrl } from "../lib/urls"
import * as siteContentFuncs from "../lib/site_content"
import { IntegrationTestHelper } from "../testing_utils"
import {
  makeSingletonConfigItem,
  makeSingletonsConfigItem,
  makeWebsiteContentDetail,
  makeWebsiteDetail,
} from "../util/factories/websites"

import {
  SingletonConfigItem,
  SingletonsConfigItem,
  Website,
  WebsiteContent,
} from "../types/websites"

// ckeditor is not working properly in tests, but we don't need to test it here so just mock it away
function mocko() {
  return <div>mock</div>
}

jest.mock("../lib/site_content", () => {
  return {
    __esModule: true,
    ...jest.requireActual("../lib/site_content"),
  }
})

jest.mock("./widgets/MarkdownEditor", () => ({
  __esModule: true,
  default: mocko,
}))

describe("SingletonsContentListing", () => {
  let helper: IntegrationTestHelper,
    website: Website,
    configItem: SingletonsConfigItem,
    singletonConfigItems: SingletonConfigItem[],
    content: WebsiteContent

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    content = makeWebsiteContentDetail()
    website = makeWebsiteDetail()
    singletonConfigItems = [
      makeSingletonConfigItem(),
      makeSingletonConfigItem(),
      makeSingletonConfigItem(),
    ]
    configItem = {
      ...makeSingletonsConfigItem(),
      files: singletonConfigItems,
    }
  })

  const setupMocks = (h: IntegrationTestHelper) => {
    h.mockGetRequest(
      siteApiContentDetailUrl
        .param({
          name: website.name,
          textId: singletonConfigItems[0].name,
        })
        .toString(),
      content,
    )
  }

  const renderListing = async (initialPath = "/") => {
    helper = new IntegrationTestHelper(initialPath)
    setupMocks(helper)

    const [result, { history }] = helper.render(
      <WebsiteContext.Provider value={website}>
        <SingletonsContentListing configItem={configItem} />
      </WebsiteContext.Provider>,
    )

    await waitFor(() => {
      expect(screen.getByRole("tablist")).toBeInTheDocument()
    })

    return { result, history }
  }

  it("should render tabs for each singleton config item, showing the first tab on load", async () => {
    await renderListing()

    const tabs = screen.getAllByRole("tab")

    expect(tabs).toHaveLength(singletonConfigItems.length)

    singletonConfigItems.forEach((item, idx) => {
      expect(tabs[idx]).toHaveTextContent(item.label)
    })

    expect(tabs[0]).toHaveClass("active")
    for (let i = 1; i < tabs.length; i++) {
      expect(tabs[i]).not.toHaveClass("active")
    }

    expect(document.querySelector("form")).toBeInTheDocument()
  })

  it("should have working tabs", async () => {
    const user = userEvent.setup()
    const tabIndexToSelect = 2

    helper = new IntegrationTestHelper()
    setupMocks(helper)
    helper.mockGetRequest(
      siteApiContentDetailUrl
        .param({
          name: website.name,
          textId: singletonConfigItems[tabIndexToSelect].name,
        })
        .toString(),
      content,
    )

    helper.render(
      <WebsiteContext.Provider value={website}>
        <SingletonsContentListing configItem={configItem} />
      </WebsiteContext.Provider>,
    )

    await waitFor(() => {
      expect(screen.getByRole("tablist")).toBeInTheDocument()
    })

    const tabs = screen.getAllByRole("tab")

    await user.click(tabs[tabIndexToSelect])

    await waitFor(() => {
      expect(tabs[tabIndexToSelect]).toHaveClass("active")
    })
  })

  it.each([
    { contentContext: true, preposition: "with" },
    { contentContext: false, preposition: "without" },
  ])(
    "loads content detail from the API if needed $preposition content context",
    async ({ contentContext }) => {
      const user = userEvent.setup()
      const needsContentContextStub = jest
        .spyOn(siteContentFuncs, "needsContentContext")
        .mockReturnValue(contentContext)

      const tabIndexToSelect = 1
      const newContent = makeWebsiteContentDetail()

      helper = new IntegrationTestHelper()

      helper.mockGetRequest(
        siteApiContentDetailUrl
          .param({
            name: website.name,
            textId: singletonConfigItems[0].name,
          })
          .query(contentContext ? { content_context: true } : {})
          .toString(),
        content,
      )

      const contentDetailUrl = siteApiContentDetailUrl
        .param({
          name: website.name,
          textId: singletonConfigItems[tabIndexToSelect].name,
        })
        .query(contentContext ? { content_context: true } : {})
        .toString()

      helper.mockGetRequest(contentDetailUrl, newContent)

      helper.render(
        <WebsiteContext.Provider value={website}>
          <SingletonsContentListing configItem={configItem} />
        </WebsiteContext.Provider>,
      )

      await waitFor(() => {
        expect(screen.getByRole("tablist")).toBeInTheDocument()
      })

      const tabs = screen.getAllByRole("tab")

      await user.click(tabs[tabIndexToSelect])

      await waitFor(() => {
        expect(helper.handleRequest).toHaveBeenCalledWith(
          contentDetailUrl,
          "GET",
          expect.anything(),
        )
      })

      expect(needsContentContextStub).toHaveBeenCalledWith(
        singletonConfigItems[tabIndexToSelect].fields,
      )

      needsContentContextStub.mockRestore()
    },
  )

  it("should render the SiteContentEditor component with correct props", async () => {
    await renderListing()

    expect(document.querySelector("form")).toBeInTheDocument()
    expect(screen.getByLabelText(/title/i)).toHaveValue(content.title)
  })

  it.each([
    { dirty: true, confirmCalls: 1 },
    { dirty: false, confirmCalls: 0 },
  ])(
    "prompts for confirmation on pathname change iff discarding dirty state [dirty=$dirty]",
    async ({ dirty, confirmCalls }) => {
      const user = userEvent.setup()

      const { history } = await renderListing()

      if (dirty) {
        const titleInput = screen.getByLabelText(/title/i)
        await user.clear(titleInput)
        await user.type(titleInput, "some changes")
      }

      expect(window.mockConfirm).toHaveBeenCalledTimes(0)

      await act(async () => {
        history.push("/elsewhere")
      })

      expect(window.mockConfirm).toHaveBeenCalledTimes(confirmCalls)
      if (confirmCalls > 0) {
        expect(window.mockConfirm.mock.calls[0][0]).toMatch(
          /Are you sure you want to discard your changes\?/,
        )
      }
    },
  )

  it.each([
    { dirty: true, confirmCalls: 1 },
    { dirty: false, confirmCalls: 0 },
  ])(
    "prompts for confirmation on publish iff state is dirty [dirty=$dirty]",
    async ({ dirty, confirmCalls }) => {
      const user = userEvent.setup()

      const { history } = await renderListing()

      if (dirty) {
        const titleInput = screen.getByLabelText(/title/i)
        await user.clear(titleInput)
        await user.type(titleInput, "some changes")
      }

      expect(window.mockConfirm).toHaveBeenCalledTimes(0)

      await act(async () => {
        history.push("?publish=")
      })

      expect(window.mockConfirm).toHaveBeenCalledTimes(confirmCalls)
      if (confirmCalls > 0) {
        expect(window.mockConfirm.mock.calls[0][0]).toMatch(
          /Are you sure you want to publish\?/,
        )
      }
    },
  )

  it.each([true, false])(
    "changes route and unmounts when dirty iff confirmed [confirmed=%p]",
    async (confirmed) => {
      const user = userEvent.setup()

      const { history } = await renderListing()

      const titleInput = screen.getByLabelText(/title/i)
      await user.clear(titleInput)
      await user.type(titleInput, "some changes")

      window.mockConfirm.mockReturnValue(confirmed)

      expect(history.location.pathname).toBe("/")

      await act(async () => {
        history.push("/elsewhere")
      })

      if (confirmed) {
        expect(history.location.pathname).toBe("/elsewhere")
      } else {
        expect(history.location.pathname).toBe("/")
      }
    },
  )

  it("clears a dirty flag when the path changes", async () => {
    const user = userEvent.setup()

    const { history } = await renderListing()

    const titleInput = screen.getByLabelText(/title/i)
    await user.clear(titleInput)
    await user.type(titleInput, "some changes")

    window.mockConfirm.mockReturnValue(true)

    await act(async () => {
      history.push("/pages")
    })

    await waitFor(() => {
      expect(history.location.pathname).toBe("/pages")
    })

    window.mockConfirm.mockClear()

    await act(async () => {
      history.push("/another-page")
    })

    expect(window.mockConfirm).toHaveBeenCalledTimes(0)
  })
})
