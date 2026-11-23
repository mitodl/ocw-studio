import React from "react"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import * as yup from "yup"

import SiteCollaboratorForm, {
  emailValidation,
  roleValidation,
} from "./SiteCollaboratorForm"
import { EDITABLE_ROLES } from "../../constants"
import { makeWebsiteCollaborator } from "../../util/factories/websites"

import { WebsiteCollaborator } from "../../types/websites"

describe("SiteCollaboratorForm", () => {
  let onSubmitStub: jest.Mock,
    onCancelStub: jest.Mock,
    collaborator: WebsiteCollaborator

  const renderForm = (collaborator: WebsiteCollaborator | null) =>
    render(
      <SiteCollaboratorForm
        collaborator={collaborator}
        onSubmit={onSubmitStub}
        onCancel={onCancelStub}
      />,
    )

  beforeEach(() => {
    onSubmitStub = jest.fn()
    onCancelStub = jest.fn()
  })

  describe("add a new collaborator", () => {
    it("passes onSubmit to Formik", async () => {
      const user = userEvent.setup()
      renderForm(null)
      await user.type(screen.getByLabelText(/email/i), "test@example.com")
      await user.click(screen.getByLabelText(/role/i))
      await user.click(screen.getByText("Administrator"))
      await user.click(screen.getByRole("button", { name: /save/i }))
      await waitFor(() => {
        expect(onSubmitStub).toHaveBeenCalled()
      })
    })

    it("shows an option for each role, plus an empty option", async () => {
      const user = userEvent.setup()
      renderForm(null)
      const roleSelect = screen.getByLabelText(/role/i)
      expect(roleSelect).toBeInTheDocument()
      await user.click(roleSelect)
      EDITABLE_ROLES.forEach((role) => {
        expect(screen.getByText(new RegExp(role, "i"))).toBeInTheDocument()
      })
    })

    it("shows an email field", () => {
      renderForm(null)
      expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
    })
  })

  describe("edit an existing collaborator", () => {
    beforeEach(() => {
      collaborator = makeWebsiteCollaborator()
    })

    it("cancel button onClick function is onCancel prop", () => {
      renderForm(null)
      const cancelButton = screen.getByRole("button", { name: /cancel/i })
      cancelButton.click()
      expect(onCancelStub).toHaveBeenCalled()
    })

    it("passes onSubmit to Formik", async () => {
      const user = userEvent.setup()
      renderForm(collaborator)
      await user.click(screen.getByRole("button", { name: /save/i }))
      await waitFor(() => {
        expect(onSubmitStub).toHaveBeenCalled()
      })
    })

    it("has current role selected", () => {
      renderForm(collaborator)
      const roleSelect = screen.getByLabelText(/role/i)
      expect(roleSelect).toBeInTheDocument()
    })

    it("shows an option for each role plus an empty choice", async () => {
      const user = userEvent.setup()
      renderForm(collaborator)
      const roleSelect = screen.getByLabelText(/role/i)
      expect(roleSelect).toBeInTheDocument()
      await user.click(roleSelect)
      EDITABLE_ROLES.forEach((role) => {
        expect(
          screen.getAllByText(new RegExp(role, "i")).length,
        ).toBeGreaterThanOrEqual(1)
      })
    })
  })

  describe("validation", () => {
    const collaboratorValidation = yup
      .object()
      .shape({ ...roleValidation, ...emailValidation })

    it("rejects an empty role", async () => {
      await expect(
        collaboratorValidation.validateAt("role", { role: "" }),
      ).rejects.toMatchObject({ errors: ["Role is a required field"] })
    })

    it("rejects an empty email", async () => {
      await expect(
        collaboratorValidation.validateAt("email", { email: "" }),
      ).rejects.toMatchObject({ errors: ["Email is a required field"] })
    })

    it("rejects an invalid email", async () => {
      await expect(
        collaboratorValidation.validateAt("email", { email: "fake.test.com" }),
      ).rejects.toMatchObject({ errors: ["Email must be a valid email"] })
    })

    it("does not reject a valid role", async () => {
      await expect(
        collaboratorValidation.validateAt("role", { role: "admin" }),
      ).resolves.toBe("admin")
    })
  })
})
