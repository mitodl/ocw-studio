import React from "react"
import sinon, { SinonStub } from "sinon"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { ValidationError } from "yup"

import PublishForm, { websiteUrlValidation } from "./PublishForm"
import { PublishingEnv } from "../../constants"
import { assertInstanceOf } from "../../test_util"
import { makeWebsiteDetail } from "../../util/factories/websites"

describe("PublishForm", () => {
  let onSubmitStub: SinonStub, website: ReturnType<typeof makeWebsiteDetail>

  const renderForm = (props = {}) =>
    render(
      <PublishForm
        onSubmit={onSubmitStub}
        disabled={false}
        website={website}
        option={PublishingEnv.Staging}
        {...props}
      />,
    )

  beforeEach(() => {
    onSubmitStub = sinon.stub()
    website = makeWebsiteDetail()
  })

  afterEach(() => {
    sinon.restore()
  })

  it("passes onSubmit to Formik", async () => {
    const user = userEvent.setup()
    website.publish_date = "2025-01-01"
    renderForm()
    const button = screen.getByRole("button", { name: /publish/i })
    await user.click(button)
    await waitFor(() => {
      expect(onSubmitStub.called).toBe(true)
    })
  })

  it.each([
    { urlPath: null, basedOn: "url_suggestion" },
    { urlPath: "courses/5.2-my-course", basedOn: "url_path" },
  ])(
    "initialValue for url_path should be based on website $basedOn",
    ({ urlPath }) => {
      website.publish_date = null
      website.url_path = urlPath
      renderForm()
      const input = screen.getByLabelText(/url/i) as HTMLInputElement
      if (urlPath) {
        expect(input).toHaveValue("5.2-my-course")
      } else {
        expect(input).toHaveValue(website.url_suggestion)
      }
    },
  )

  it("shows a field for URL Path if website is not published", () => {
    website.publish_date = null
    renderForm()
    expect(screen.getByLabelText(/url/i)).toBeInTheDocument()
  })

  it.each([PublishingEnv.Staging, PublishingEnv.Production])(
    "shows a URL link instead of a field if website is published",
    (option) => {
      website.publish_date = "2020-01-01"
      website.url_path = "courses/my-url-fall-2028"
      renderForm({ option: option })
      expect(screen.queryByLabelText(/url/i)).not.toBeInTheDocument()
      const link = screen.getByRole("link")
      expect(link).toHaveAttribute(
        "href",
        option === PublishingEnv.Staging ? website.draft_url : website.live_url,
      )
    },
  )

  it("shows a text-only live url for unpublished site", () => {
    website.publish_date = null
    website.url_path = "courses/my-url-fall-2028"
    renderForm({ option: PublishingEnv.Production })
    expect(screen.queryByRole("link")).not.toBeInTheDocument()
    expect(screen.getByText(website.live_url)).toBeInTheDocument()
  })

  describe("validation", () => {
    it("rejects an empty url", async () => {
      try {
        await expect(
          await websiteUrlValidation.validateAt("url_path", { url_path: "" }),
        ).rejects.toThrow()
      } catch (error) {
        assertInstanceOf(error, ValidationError)
        expect(error.errors).toStrictEqual(["URL Path is a required field"])
      }
    })
    it("rejects a URL Path with invalid characters", async () => {
      try {
        await expect(
          await websiteUrlValidation.validateAt("url_path", {
            url_path: "courses/bad-url-fall-2024",
          }),
        ).rejects.toThrow()
      } catch (error) {
        assertInstanceOf(error, ValidationError)
        expect(error.errors).toStrictEqual([
          "Only alphanumeric characters, periods, dashes, or underscores allowed",
        ])
      }
    })
  })
})
