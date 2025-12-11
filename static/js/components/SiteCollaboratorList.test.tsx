import React from "react"
import { screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import SiteCollaboratorList from "./SiteCollaboratorList"
import {
  siteApiCollaboratorsUrl,
  siteApiCollaboratorsDetailUrl,
} from "../lib/urls"
import {
  makePermanentWebsiteCollaborator,
  makeWebsiteDetail,
  makeWebsiteCollaborators,
} from "../util/factories/websites"
import { IntegrationTestHelper } from "../testing_utils"
import WebsiteContext from "../context/Website"

import { Website, WebsiteCollaborator } from "../types/websites"
import { WebsiteCollaboratorListingResponse } from "../query-configs/websites"

describe("SiteCollaboratorList", () => {
  let helper: IntegrationTestHelper,
    website: Website,
    collaborators: WebsiteCollaborator[],
    permanentAdmin: WebsiteCollaborator[],
    apiResponse: WebsiteCollaboratorListingResponse

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    website = makeWebsiteDetail()
    collaborators = makeWebsiteCollaborators()
    permanentAdmin = [makePermanentWebsiteCollaborator()]
    collaborators = [...collaborators, ...permanentAdmin]

    apiResponse = {
      results: collaborators,
      count: 6,
      next: null,
      previous: null,
    }
    helper.mockGetRequest(
      siteApiCollaboratorsUrl
        .param({
          name: website.name,
        })
        .query({ offset: 0 })
        .toString(),
      apiResponse,
    )
  })

  const renderList = async () => {
    const [result, { history }] = helper.render(
      <WebsiteContext.Provider value={website}>
        <SiteCollaboratorList />
      </WebsiteContext.Provider>,
    )

    await waitFor(() => {
      expect(screen.getByText(collaborators[0].name)).toBeInTheDocument()
    })

    return { result, history }
  }

  it("sets the document title", async () => {
    await renderList()

    await waitFor(() => {
      expect(document.title).toContain(website.title)
      expect(document.title).toContain("Collaborators")
    })
  })

  it("renders the collaborators list with expected number of items", async () => {
    await renderList()

    const numCollaborators = collaborators.length

    for (const collaborator of collaborators) {
      expect(screen.getByText(collaborator.name)).toBeInTheDocument()
    }

    const menuButtons = screen.getAllByRole("button", { name: /more_vert/i })
    expect(menuButtons).toHaveLength(numCollaborators - 1)
  })

  it("the edit collaborator icon sets correct state and opens the modal", async () => {
    const user = userEvent.setup()
    await renderList()

    const menuButtons = screen.getAllByRole("button", { name: /more_vert/i })
    await user.click(menuButtons[0])

    const editButton = await screen.findByRole("button", { name: /settings/i })
    await user.click(editButton)

    const dialog = await screen.findByRole("dialog")
    expect(dialog).toBeInTheDocument()
    expect(
      within(dialog).getByText(new RegExp(collaborators[0].email)),
    ).toBeInTheDocument()

    const closeButton = within(dialog).getByRole("button", { name: /close/i })
    await user.click(closeButton)

    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    })
  })

  it("the delete collaborator dialog works as expected", async () => {
    const user = userEvent.setup()
    const collaborator = collaborators[0]

    helper.mockDeleteRequest(
      siteApiCollaboratorsDetailUrl
        .param({
          name: website.name,
          userId: collaborator.user_id,
        })
        .toString(),
      {},
    )

    await renderList()

    const menuButtons = screen.getAllByRole("button", { name: /more_vert/i })
    await user.click(menuButtons[0])

    const deleteButton = await screen.findByRole("button", { name: /delete/i })
    await user.click(deleteButton)

    const dialog = await screen.findByRole("dialog")
    expect(dialog).toBeInTheDocument()
    expect(dialog).toHaveTextContent(collaborator.name)

    const confirmButton = within(dialog)
      .getAllByRole("button")
      .find((btn) => btn.textContent?.toLowerCase().includes("delete"))
    expect(confirmButton).toBeInTheDocument()
    await user.click(confirmButton!)

    await waitFor(() => {
      expect(helper.handleRequest).toHaveBeenCalledWith(
        siteApiCollaboratorsDetailUrl
          .param({
            name: website.name,
            userId: collaborator.user_id,
          })
          .toString(),
        "DELETE",
        expect.anything(),
      )
    })

    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    })
  })

  it("the add collaborator button sets correct state and opens the modal", async () => {
    const user = userEvent.setup()
    await renderList()

    const addButton = screen.getByRole("button", { name: /add/i })
    await user.click(addButton)

    const dialog = await screen.findByRole("dialog")
    expect(dialog).toBeInTheDocument()
    expect(within(dialog).getByText(/add collaborator/i)).toBeInTheDocument()

    const closeButton = within(dialog).getByRole("button", { name: /close/i })
    await user.click(closeButton)

    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    })
  })
})
