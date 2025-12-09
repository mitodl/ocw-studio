import React from "react"
import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import SiteCreationPage from "./SiteCreationPage"
import IntegrationTestHelper from "../testing_utils/IntegrationTestHelper"
import {
  makeWebsiteDetail,
  makeWebsiteStarter,
} from "../util/factories/websites"
import { siteDetailUrl, siteApi, startersApi } from "../lib/urls"

import { Website, WebsiteStarter } from "../types/websites"

describe("SiteCreationPage", () => {
  let helper: IntegrationTestHelper,
    starters: Array<WebsiteStarter>,
    website: Website,
    historyPushStub: jest.Mock

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    starters = [makeWebsiteStarter(), makeWebsiteStarter()]
    website = makeWebsiteDetail()
    historyPushStub = jest.fn()

    helper.mockGetRequest(startersApi.toString(), starters)
  })

  const renderPage = () => {
    const [result, { history }] = helper.render(
      <SiteCreationPage history={{ push: historyPushStub } as any} />,
    )
    return { ...result, history }
  }

  it("renders a form with the right props", async () => {
    renderPage()
    await waitFor(() => {
      expect(screen.getByLabelText(/title/i)).toBeInTheDocument()
    })
    expect(screen.getByLabelText(/short id/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/starter/i)).toBeInTheDocument()
  })

  it("sets the page title", async () => {
    renderPage()
    await waitFor(() => {
      expect(document.title).toContain("New Site")
    })
  })

  describe("passes a form submit function", () => {
    const errorMsg = "Error"

    it("that creates a new site and redirect on success", async () => {
      const user = userEvent.setup()
      helper.mockPostRequest(siteApi.toString(), website)
      renderPage()

      await waitFor(() => {
        expect(screen.getByLabelText(/title/i)).toBeInTheDocument()
      })

      await user.type(screen.getByLabelText(/title/i), "My Title")
      await user.type(screen.getByLabelText(/short id/i), "My-Title")

      await user.click(screen.getByRole("button", { name: /save/i }))

      await waitFor(() => {
        expect(historyPushStub).toHaveBeenCalledTimes(1)
      })
      expect(historyPushStub).toHaveBeenCalledWith(
        siteDetailUrl.param({ name: website.name }).toString(),
      )
    })

    it("that sets form errors if the API request fails", async () => {
      const user = userEvent.setup()
      const errorResp = {
        errors: {
          title: errorMsg,
        },
      }
      helper.mockPostRequest(siteApi.toString(), errorResp, 400)
      renderPage()

      await waitFor(() => {
        expect(screen.getByLabelText(/title/i)).toBeInTheDocument()
      })

      await user.type(screen.getByLabelText(/title/i), errorMsg)
      await user.type(screen.getByLabelText(/short id/i), "my-site")

      await user.click(screen.getByRole("button", { name: /save/i }))

      await waitFor(() => {
        expect(screen.getByText(errorMsg)).toBeInTheDocument()
      })
      expect(historyPushStub).not.toHaveBeenCalled()
    })

    it("that sets a status if the API request fails with a string error message", async () => {
      const user = userEvent.setup()
      const errorResp = {
        errors: errorMsg,
      }
      helper.mockPostRequest(siteApi.toString(), errorResp, 400)
      renderPage()

      await waitFor(() => {
        expect(screen.getByLabelText(/title/i)).toBeInTheDocument()
      })

      await user.type(screen.getByLabelText(/title/i), "My Title")
      await user.type(screen.getByLabelText(/short id/i), "My-Title")

      await user.click(screen.getByRole("button", { name: /save/i }))

      await waitFor(() => {
        expect(screen.getByText(errorMsg)).toBeInTheDocument()
      })
      expect(historyPushStub).not.toHaveBeenCalled()
    })
  })
})
