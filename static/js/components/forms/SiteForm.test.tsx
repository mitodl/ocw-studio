import React from "react"
import sinon, { SinonStub } from "sinon"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { SiteForm, websiteValidation } from "./SiteForm"
import { makeWebsiteStarter } from "../../util/factories/websites"

import { WebsiteStarter } from "../../types/websites"

describe("SiteForm", () => {
  let sandbox: sinon.SinonSandbox,
    onSubmitStub: SinonStub,
    websiteStarters: Array<WebsiteStarter>

  const renderForm = () =>
    render(
      <SiteForm onSubmit={onSubmitStub} websiteStarters={websiteStarters} />,
    )

  beforeEach(() => {
    sandbox = sinon.createSandbox()
    onSubmitStub = sandbox.stub()
    websiteStarters = [makeWebsiteStarter(), makeWebsiteStarter()]
  })

  afterEach(() => {
    sandbox.restore()
  })

  it("passes onSubmit to Formik", () => {
    renderForm()
    expect(screen.getByRole("button", { name: /save/i })).toBeInTheDocument()
  })

  it("renders a Site Type select field", () => {
    renderForm()
    expect(screen.getByLabelText(/site type/i)).toBeInTheDocument()
  })

  it("shows an option for each website starter", async () => {
    renderForm()
    const user = userEvent.setup()
    expect(screen.getByText(/starter/i)).toBeInTheDocument()
    const selectInput = screen.getByRole("textbox", { name: "Starter*" })
    await user.click(selectInput)
    for (const starter of websiteStarters) {
      expect(screen.getAllByText(starter.name).length).toBeGreaterThanOrEqual(1)
    }
  })

  describe("validation", () => {
    it("rejects an empty title", async () => {
      await expect(
        websiteValidation.validateAt("title", { title: "" }),
      ).rejects.toThrow("Title is a required field")
    })
    it("rejects a short_id with invalid characters", async () => {
      await expect(
        websiteValidation.validateAt("short_id", {
          short_id: "Bad ID!",
        }),
      ).rejects.toThrow(
        "Only alphanumeric characters, periods, dashes, or underscores allowed",
      )
    })
    it("rejects an empty site_type", async () => {
      await expect(
        websiteValidation.validateAt("site_type", { site_type: "" }),
      ).rejects.toThrow("Site Type is a required field")
    })
  })
})
