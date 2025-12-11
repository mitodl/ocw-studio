import React from "react"
import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import MenuItemForm from "./MenuItemForm"

import { WebsiteContent } from "../../types/websites"
import { makeWebsiteContentDetail } from "../../util/factories/websites"
import { IntegrationTestHelper } from "../../testing_utils"
import { siteApiContentListingUrl } from "../../lib/urls"
import { makeWebsiteDetail } from "../../util/factories/websites"
import WebsiteContext from "../../context/Website"

describe("MenuItemForm", () => {
  let helper: IntegrationTestHelper,
    onSubmitStub: jest.Mock,
    contentContext: WebsiteContent[]

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    onSubmitStub = jest.fn()
    contentContext = [makeWebsiteContentDetail(), makeWebsiteContentDetail()]
  })

  const renderForm = async (props = {}) => {
    const website = makeWebsiteDetail()

    helper.mockGetRequest(
      siteApiContentListingUrl
        .query({
          detailed_list: true,
          content_context: true,
          page_content: true,
          offset: 0,
        })
        .param({ name: website.name })
        .toString(),
      { results: contentContext, next: null },
    )

    const [result] = helper.render(
      <WebsiteContext.Provider value={website}>
        <MenuItemForm
          activeItem={null}
          onSubmit={onSubmitStub}
          contentContext={contentContext}
          {...props}
        />
      </WebsiteContext.Provider>,
    )

    await waitFor(() => {
      expect(screen.getByRole("form")).toBeInTheDocument()
    })
    return { result, website }
  }

  it("calls the onSubmit method", async () => {
    const user = userEvent.setup()
    await renderForm()

    const titleInput = screen.getByLabelText(/title/i)
    await user.type(titleInput, "Test Title")

    const submitBtn = screen.getByRole("button", { name: /save/i })
    expect(submitBtn).toHaveAttribute("type", "submit")
  })

  it("renders with the correct initial values if given a null active item", async () => {
    await renderForm({ activeItem: null })

    const titleInput = screen.getByLabelText(/title/i) as HTMLInputElement
    expect(titleInput.value).toBe("")
  })

  it("renders with the correct initial values if given an active item with link", async () => {
    const activeItem = {
      id: "item-id",
      text: "text",
      targetContentId: "content-id",
      targetUrl: null,
    }
    await renderForm({ activeItem })

    const titleInput = screen.getByLabelText(/title/i) as HTMLInputElement
    expect(titleInput.value).toBe(activeItem.text)
  })

  it("renders a link dropdown", async () => {
    await renderForm()

    expect(screen.getByText(/link to/i)).toBeInTheDocument()
  })

  it("renders a RelationField with the right label", async () => {
    const existingMenuIds = new Set(["abc", "def"])
    const collections = ["page"]
    const website = makeWebsiteDetail()

    helper.mockGetRequest(
      siteApiContentListingUrl
        .query({
          detailed_list: true,
          content_context: true,
          type: collections,
          offset: 0,
        })
        .param({ name: website.name })
        .toString(),
      { results: contentContext, next: null },
    )

    helper.render(
      <WebsiteContext.Provider value={website}>
        <MenuItemForm
          activeItem={null}
          onSubmit={onSubmitStub}
          contentContext={contentContext}
          existingMenuIds={existingMenuIds}
          collections={collections}
        />
      </WebsiteContext.Provider>,
    )

    await waitFor(() => {
      expect(screen.getByRole("form")).toBeInTheDocument()
    })

    expect(screen.getByText(/link to/i)).toBeInTheDocument()
  })
})
