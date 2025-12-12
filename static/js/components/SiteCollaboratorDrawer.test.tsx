import React from "react"
import { screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import sinon, { SinonStub } from "sinon"

import SiteCollaboratorDrawer from "./SiteCollaboratorDrawer"
import IntegrationTestHelper from "../testing_utils/IntegrationTestHelper"
import {
  makeWebsiteDetail,
  makeWebsiteCollaborator,
} from "../util/factories/websites"
import {
  siteApiCollaboratorsDetailUrl,
  siteApiCollaboratorsUrl,
} from "../lib/urls"

import { Website, WebsiteCollaborator } from "../types/websites"

const errorMsg = "Error"

describe("SiteCollaboratorDrawerTest", () => {
  let helper: IntegrationTestHelper,
    website: Website,
    toggleVisibilityStub: SinonStub,
    collaborator: WebsiteCollaborator

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    website = makeWebsiteDetail()
    collaborator = makeWebsiteCollaborator()
    toggleVisibilityStub = sinon.stub()
  })

  afterEach(() => {
    sinon.restore()
  })

  const renderDrawer = (props = {}) => {
    const defaultProps = {
      collaborator: null as WebsiteCollaborator | null,
      visibility: true,
      siteName: website.name,
      toggleVisibility: toggleVisibilityStub,
      fetchWebsiteCollaboratorListing: jest.fn(),
    }

    return helper.render(
      <SiteCollaboratorDrawer {...defaultProps} {...props} />,
    )
  }

  describe("Edit an existing collaborator", () => {
    it("renders a form with the right props", async () => {
      const [{ unmount }] = renderDrawer({ collaborator })
      expect(screen.getByRole("button", { name: /save/i })).toBeInTheDocument()
      expect(
        screen.getByRole("button", { name: /cancel/i }),
      ).toBeInTheDocument()
      expect(screen.getByLabelText(/role/i)).toBeInTheDocument()
      unmount()
    })

    it("renders a modal header containing the collaborator email", async () => {
      const [{ unmount }] = renderDrawer({ collaborator })
      expect(screen.getByText(`Edit ${collaborator.email}`)).toBeInTheDocument()
      unmount()
    })

    it("pre-populates the role field with the collaborator's current role", async () => {
      const [{ unmount }] = renderDrawer({ collaborator })
      const dialog = screen.getByRole("dialog")
      expect(
        within(dialog).getByText(/editor|administrator|owner/i),
      ).toBeInTheDocument()
      unmount()
    })

    it("edits a collaborator role and closes the dialog on success", async () => {
      const user = userEvent.setup()
      helper.mockPatchRequest(
        siteApiCollaboratorsDetailUrl
          .param({
            name: website.name,
            userId: collaborator.user_id,
          })
          .toString(),
        collaborator,
        200,
      )

      const [{ unmount }] = renderDrawer({ collaborator })

      const submitButton = screen.getByRole("button", { name: /save/i })
      await user.click(submitButton)

      await waitFor(() => {
        expect(helper.handleRequest).toHaveBeenCalledWith(
          siteApiCollaboratorsDetailUrl
            .param({
              name: website.name,
              userId: collaborator.user_id,
            })
            .toString(),
          "PATCH",
          expect.anything(),
        )
      })

      await waitFor(() => {
        expect(toggleVisibilityStub.called).toBe(true)
      })

      unmount()
    })

    it("sets form errors if the API request fails", async () => {
      const user = userEvent.setup()
      const errorResp = {
        errors: {
          role: errorMsg,
        },
      }
      helper.mockPatchRequest(
        siteApiCollaboratorsDetailUrl
          .param({
            name: website.name,
            userId: collaborator.user_id,
          })
          .toString(),
        errorResp,
        400,
      )

      const [{ unmount }] = renderDrawer({ collaborator })

      const submitButton = screen.getByRole("button", { name: /save/i })
      await user.click(submitButton)

      await waitFor(() => {
        expect(screen.getByText(errorMsg)).toBeInTheDocument()
      })

      expect(toggleVisibilityStub.called).toBe(false)

      unmount()
    })

    it("sets form errors if the API request fails with a string error message", async () => {
      const user = userEvent.setup()
      const errorResp = {
        errors: errorMsg,
      }
      helper.mockPatchRequest(
        siteApiCollaboratorsDetailUrl
          .param({
            name: website.name,
            userId: collaborator.user_id,
          })
          .toString(),
        errorResp,
        400,
      )

      const [{ unmount }] = renderDrawer({ collaborator })

      const submitButton = screen.getByRole("button", { name: /save/i })
      await user.click(submitButton)

      await waitFor(() => {
        expect(screen.getByText(errorMsg)).toBeInTheDocument()
      })

      expect(toggleVisibilityStub.called).toBe(false)

      unmount()
    })

    it("calls toggleVisibility when close button is clicked", async () => {
      const user = userEvent.setup()

      const [{ unmount }] = renderDrawer({ collaborator })

      const closeButton = screen.getByRole("button", { name: /close/i })
      await user.click(closeButton)

      expect(toggleVisibilityStub.called).toBe(true)

      unmount()
    })
  })

  describe("Create a new collaborator", () => {
    it("renders a modal header containing expected text", async () => {
      const [{ unmount }] = renderDrawer()
      expect(screen.getByText("Add collaborator")).toBeInTheDocument()
      unmount()
    })

    it("renders email and role fields for new collaborator", async () => {
      const [{ unmount }] = renderDrawer()
      expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/role/i)).toBeInTheDocument()
      expect(screen.getByRole("button", { name: /save/i })).toBeInTheDocument()
      expect(
        screen.getByRole("button", { name: /cancel/i }),
      ).toBeInTheDocument()
      unmount()
    })

    it("renders an email input field", async () => {
      const [{ unmount }] = renderDrawer()
      expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
      unmount()
    })

    it("shows validation errors when submitting without required fields", async () => {
      const user = userEvent.setup()

      const [{ unmount }] = renderDrawer()

      const submitButton = screen.getByRole("button", { name: /save/i })
      await user.click(submitButton)

      await waitFor(() => {
        expect(
          screen.getByText(/role is a required field/i),
        ).toBeInTheDocument()
      })

      unmount()
    })

    it("creates a new collaborator and closes the dialog on success", async () => {
      const user = userEvent.setup()
      const newCollaborator = makeWebsiteCollaborator()
      const fetchWebsiteCollaboratorListing = jest.fn()

      helper.mockPostRequest(
        siteApiCollaboratorsUrl.param({ name: website.name }).toString(),
        newCollaborator,
        201,
      )

      const [{ unmount }] = renderDrawer({ fetchWebsiteCollaboratorListing })

      const emailInput = screen.getByLabelText(/email/i)
      await user.type(emailInput, newCollaborator.email)
      const roleSelect = screen.getByLabelText(/role/i)
      await user.click(roleSelect)
      const editorOption = await screen.findByText(/editor/i)
      await user.click(editorOption)

      const submitButton = screen.getByRole("button", { name: /save/i })
      await user.click(submitButton)

      await waitFor(() => {
        expect(helper.handleRequest).toHaveBeenCalledWith(
          siteApiCollaboratorsUrl.param({ name: website.name }).toString(),
          "POST",
          expect.anything(),
        )
      })

      await waitFor(() => {
        expect(toggleVisibilityStub.called).toBe(true)
      })

      unmount()
    })

    it("calls cancel handler when cancel is clicked", async () => {
      const user = userEvent.setup()

      const [{ unmount }] = renderDrawer()

      const cancelButton = screen.getByRole("button", { name: /cancel/i })
      await user.click(cancelButton)

      expect(toggleVisibilityStub.called).toBe(true)

      unmount()
    })

    it("calls toggleVisibility when close button is clicked", async () => {
      const user = userEvent.setup()

      const [{ unmount }] = renderDrawer()

      const closeButton = screen.getByRole("button", { name: /close/i })
      await user.click(closeButton)

      expect(toggleVisibilityStub.called).toBe(true)

      unmount()
    })

    it("does not render email field when editing existing collaborator", async () => {
      const [{ unmount }] = renderDrawer({ collaborator })
      expect(screen.queryByLabelText(/email/i)).not.toBeInTheDocument()
      unmount()
    })
  })

  describe("Modal visibility", () => {
    it("does not render when visibility is false", async () => {
      const [{ unmount }] = renderDrawer({ visibility: false })
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
      unmount()
    })

    it("renders when visibility is true", async () => {
      const [{ unmount }] = renderDrawer({ visibility: true })
      expect(screen.getByRole("dialog")).toBeInTheDocument()
      unmount()
    })
  })
})
