import React from "react"
import moment from "moment"
import { isEmpty } from "ramda"

import { siteApiActionUrl, siteApiDetailUrl } from "../lib/urls"
import { assertInstanceOf, shouldIf } from "../test_util"
import { makeWebsiteDetail } from "../util/factories/websites"

import App from "../pages/App"
import { IntegrationTestHelper } from "../testing_utils"

import PublishDrawer from "./PublishDrawer"

import { Website } from "../types/websites"
import userEvent from "@testing-library/user-event"
import { waitFor, screen, within, cleanup } from "@testing-library/react"
import * as dom from "@testing-library/dom"
import _ from "lodash"

describe("PublishDrawer", () => {
  let helper: IntegrationTestHelper,
    website: Website,
    toggleVisibilityStub: jest.Mock

  beforeEach(() => {
    website = {
      ...makeWebsiteDetail(),
      has_unpublished_draft: true,
      has_unpublished_live: true,
      is_admin: true,
      url_path: "mysite-fall-2025",
      draft_publish_status: "succeeded",
      live_publish_status: "succeeded",
    }
    toggleVisibilityStub = jest.fn()
    helper = new IntegrationTestHelper()
    helper.mockGetRequest(
      siteApiDetailUrl.param({ name: website.name }).toString(),
      website,
    )
  })

  afterEach(() => {
    cleanup()
  })

  const renderDrawer = (
    props: Partial<React.ComponentProps<typeof PublishDrawer>> = {},
  ) => {
    return helper.render(
      <PublishDrawer
        website={website}
        visibility={true}
        toggleVisibility={toggleVisibilityStub}
        {...props}
      />,
    )
  }

  describe.each([
    {
      action: "staging",
      api: "preview",
      unpublishedField: "has_unpublished_draft",
      label: "Staging",
      urlField: "draft_url",
      publishDateField: "draft_publish_date",
      publishStatusField: "draft_publish_status",
      lastPublishedText: "Last staged:",
      unpublishedChangesText: "You have changes that have not been Staged.",
    },
    {
      action: "production",
      api: "publish",
      unpublishedField: "has_unpublished_live",
      label: "Production",
      urlField: "live_url",
      publishDateField: "publish_date",
      publishStatusField: "live_publish_status",
      lastPublishedText: "Last Published to Production:",
      unpublishedChangesText:
        "You have changes that have not been Published to Production.",
    },
  ])(
    "$action",
    ({
      action,
      api,
      unpublishedField,
      label,
      urlField,
      publishDateField,
      publishStatusField,
      lastPublishedText,
      unpublishedChangesText,
    }) => {
      ;[true, false].forEach((visible) => {
        it(`renders inside a Modal when visibility=${visible}`, async () => {
          renderDrawer({ visibility: visible })
          if (visible) {
            await waitFor(() => {
              expect(screen.getByRole("dialog")).toBeInTheDocument()
            })
          } else {
            expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
          }
        })
      })

      it("renders the date and url", async () => {
        const user = userEvent.setup()
        renderDrawer()
        const dialog = await screen.findByRole("dialog")
        const radioButton = within(dialog).getByLabelText(label)
        await user.click(radioButton)

        const formattedDate = moment(website[publishDateField]).format(
          "dddd, MMMM D h:mma ZZ",
        )
        expect(dialog).toHaveTextContent(lastPublishedText)
        expect(dialog).toHaveTextContent(formattedDate)

        const link = within(dialog).getByRole("link", {
          name: website[urlField],
        })
        expect(link).toHaveAttribute("href", website[urlField])
        expect(link).toHaveAttribute("target", "_blank")
      })

      it("renders the publish status", async () => {
        const user = userEvent.setup()
        renderDrawer()
        const dialog = await screen.findByRole("dialog")
        const radioButton = within(dialog).getByLabelText(label)
        await user.click(radioButton)

        expect(dialog).toHaveTextContent(
          new RegExp(website[publishStatusField] as string, "i"),
        )
      })

      it("renders a message if there is no date", async () => {
        website[publishDateField] = null
        const user = userEvent.setup()
        renderDrawer()
        const dialog = await screen.findByRole("dialog")
        const radioButton = within(dialog).getByLabelText(label)
        await user.click(radioButton)

        expect(dialog).toHaveTextContent(`${lastPublishedText}`)
        expect(dialog).toHaveTextContent("never")
      })

      it("has an option with the right label", async () => {
        renderDrawer()
        const dialog = await screen.findByRole("dialog")
        expect(within(dialog).getByLabelText(label)).toBeInTheDocument()
      })

      it("publish button is enabled even with no unpublished content", async () => {
        website[unpublishedField] = false
        const user = userEvent.setup()
        renderDrawer()
        const dialog = await screen.findByRole("dialog")
        const radioButton = within(dialog).getByLabelText(label)
        await user.click(radioButton)

        const publishButton = within(dialog).getByRole("button", {
          name: /publish/i,
        })
        expect(publishButton).not.toBeDisabled()
      })

      it("render only the preview button if user is not an admin", async () => {
        website["is_admin"] = false
        renderDrawer()
        const dialog = await screen.findByRole("dialog")
        if (action === "staging") {
          expect(within(dialog).getByLabelText(label)).toBeInTheDocument()
        } else {
          expect(within(dialog).queryByLabelText(label)).not.toBeInTheDocument()
        }
      })

      it("renders a message about unpublished content", async () => {
        website[unpublishedField] = true
        const user = userEvent.setup()
        renderDrawer()
        const dialog = await screen.findByRole("dialog")
        const radioButton = within(dialog).getByLabelText(label)
        await user.click(radioButton)

        expect(dialog).toHaveTextContent(unpublishedChangesText)
      })
      ;[[], ["error 1", "error2"]].forEach((warnings) => {
        it(`${shouldIf(
          warnings && !isEmpty(warnings),
        )} render a warning about missing content`, async () => {
          website["content_warnings"] = warnings
          renderDrawer()
          const dialog = await screen.findByRole("dialog")
          if (!isEmpty(warnings)) {
            warnings.forEach((warning) =>
              expect(dialog).toHaveTextContent(warning),
            )
          }
        })
      })

      it("publish button sends the expected request", async () => {
        const user = userEvent.setup()
        helper.mockPostRequest(
          siteApiActionUrl
            .param({
              name: website.name,
              action: api,
            })
            .toString(),
          {
            url_path: website.url_path,
          },
          200,
        )

        renderDrawer()
        const dialog = await screen.findByRole("dialog")
        const radioButton = within(dialog).getByLabelText(label)
        await user.click(radioButton)

        const publishButton = within(dialog).getByRole("button", {
          name: /publish/i,
        })
        expect(publishButton).not.toBeDisabled()
        await user.click(publishButton)

        await waitFor(() => {
          expect(helper.handleRequest).toHaveBeenCalledWith(
            `/api/websites/${website.name}/${api}/`,
            "POST",
            expect.anything(),
          )
        })

        await waitFor(() => {
          expect(toggleVisibilityStub).toHaveBeenCalled()
        })
      })
    },
  )
})

describe.each([
  {
    publishToLabel: "Production",
    api: "publish",
  },
  {
    publishToLabel: "Staging",
    api: "preview",
  },
])("Publishing Drawer Errors ($publishToLabel)", ({ publishToLabel, api }) => {
  afterEach(() => {
    cleanup()
  })

  const setup = (websiteDetails: Partial<Website> = {}) => {
    const website = makeWebsiteDetail({ is_admin: true, ...websiteDetails })
    const user = userEvent.setup()
    const helper = new IntegrationTestHelper(`/sites/${website.name}?publish=`)
    helper.mockGetWebsiteDetail(website)
    const publishUrl = siteApiActionUrl
      .param({ name: website.name, action: api })
      .toString()
    const setPublishResult = _.partial(helper.mockPostRequest, publishUrl)
    const [result] = helper.render(<App />)
    return { user, result, setPublishResult }
  }

  it("renders a generic error message if publihing API failed", async () => {
    const { user, result, setPublishResult } = setup()
    const dialog = await screen.findByRole("dialog")
    const envButton = await dom.findByText(dialog, publishToLabel)
    await user.click(envButton)

    const publishButton = await dom.findByText(dialog, "Publish")
    setPublishResult(undefined, 500)
    await user.click(publishButton)

    await waitFor(() => {
      expect(dialog).toHaveTextContent(
        "We apologize, there was a problem publishing your site.",
      )
    })
    result.unmount()
  })

  it("renders a specific error for url issues", async () => {
    const { user, result, setPublishResult } = setup({
      publish_date: null,
      url_path: "some_path_in_use",
    })
    const dialog = await screen.findByRole("dialog")
    const envButton = await dom.findByText(dialog, publishToLabel)
    await user.click(envButton)

    const publishButton = await dom.findByText(dialog, "Publish")
    setPublishResult({ url_path: "Some url error" }, 400)
    await user.click(publishButton)

    await waitFor(() => {
      expect(dialog).toHaveTextContent(
        "We apologize, there was a problem publishing your site.",
      )
    })
    const errorMsg = await dom.findByText(dialog, "Some url error")
    assertInstanceOf(errorMsg.previousSibling, HTMLInputElement)
    expect(errorMsg.previousSibling.name).toBe("url_path")
    result.unmount()
  })
})
