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

    await screen.findByTestId("menu-item-form")
    return { result, website }
  }

  it("calls the onSubmit method when form is submitted with valid data", async () => {
    const user = userEvent.setup()
    const activeItem = {
      id: "item-id",
      text: "Test Title",
      targetContentId: contentContext[0].text_id,
      targetUrl: null,
    }
    await renderForm({ activeItem })

    const submitBtn = screen.getByRole("button", { name: /save/i })
    expect(submitBtn).toHaveAttribute("type", "submit")
    await user.click(submitBtn)

    await waitFor(() => {
      expect(onSubmitStub).toHaveBeenCalled()
    })
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

  it("renders a RelationField and accepts collections and existingMenuIds props", async () => {
    const existingMenuIds = new Set(["abc", "def"])
    const collections = ["page"]
    const website = makeWebsiteDetail()

    jest.spyOn(global, "fetch").mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          results: contentContext,
          next: null,
        }),
    } as Response)

    const [{ unmount }] = helper.render(
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

    await screen.findByTestId("menu-item-form")

    expect(screen.getByText(/link to/i)).toBeInTheDocument()

    const fetchMock = global.fetch as jest.Mock
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled()
    })

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining("type%5B0%5D=page"),
      expect.anything(),
    )

    unmount()
    jest.restoreAllMocks()
  })
})
