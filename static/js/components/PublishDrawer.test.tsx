import React from "react"
import { ReactWrapper } from "enzyme"
import moment from "moment"
import sinon, { SinonStub } from "sinon"
import { act } from "react-dom/test-utils"
import { isEmpty } from "ramda"

import { siteApiActionUrl, siteApiDetailUrl } from "../lib/urls"
import { assertInstanceOf, assertNotNil, shouldIf } from "../test_util"
import { makeWebsiteDetail } from "../util/factories/websites"
import IntegrationTestHelperOld, {
  TestRenderer,
} from "../util/integration_test_helper_old"

import App from "../pages/App"
import { IntegrationTestHelper } from "../testing_utils"

import PublishDrawer from "./PublishDrawer"

import { Website } from "../types/websites"
import userEvent from "@testing-library/user-event"
import { waitFor, screen } from "@testing-library/react"
import * as dom from "@testing-library/dom"
import _ from "lodash"

const simulateClickRadio = (wrapper: ReactWrapper, idx: number) =>
  act(async () => {
    const onChange = wrapper
      .find("input[type='radio']")
      .at(idx)
      .prop("onChange")
    assertNotNil(onChange)
    // @ts-expect-error Not simulating the whole event
    onChange({ target: { checked: true } })
  })

const simulateClickPublish = (wrapper: ReactWrapper, action: string) =>
  act(async () => {
    const onChange = wrapper.find(`#publish-${action}`).prop("onChange")
    assertNotNil(onChange)
    // @ts-expect-error Not mocking whole object
    onChange({ target: { checked: true } })
  })

describe("PublishDrawer", () => {
  let helper: IntegrationTestHelperOld,
    website: Website,
    render: TestRenderer,
    toggleVisibilityStub: SinonStub,
    refreshWebsiteStub: SinonStub

  beforeEach(() => {
    helper = new IntegrationTestHelperOld()
    toggleVisibilityStub = helper.sandbox.stub()
    website = {
      ...makeWebsiteDetail(),
      has_unpublished_draft: true,
      has_unpublished_live: true,
      is_admin: true,
      url_path: "mysite-fall-2025",
    }
    refreshWebsiteStub = helper.mockGetRequest(
      siteApiDetailUrl.param({ name: website.name }).toString(),
      website,
    )
    render = helper.configureRenderer(
      PublishDrawer,
      {
        website,
        visibility: true,
        toggleVisibility: toggleVisibilityStub,
      },
      {
        entities: {},
        queries: {},
      },
    )

    helper.mockGetRequest(
      siteApiDetailUrl.param({ name: website.name }).toString(),
      website,
    )
  })

  afterEach(() => {
    helper.cleanup()
  })

  describe.each([
    {
      action: "staging",
      api: "preview",
      unpublishedField: "has_unpublished_draft",
      label: "Staging",
      urlField: "draft_url",
      publishDateField: "draft_publish_date",
      publishStatusField: "draft_publish_status",
      hasSiteMetaData: "has_site_metadata",
      idx: 0,
    },
    {
      action: "production",
      api: "publish",
      unpublishedField: "has_unpublished_live",
      label: "Production",
      urlField: "live_url",
      publishDateField: "publish_date",
      publishStatusField: "live_publish_status",
      hasSiteMetaData: "has_site_metadata",
      idx: 1,
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
      hasSiteMetaData,
      idx,
    }) => {
      ;[true, false].forEach((visible) => {
        it(`renders inside a Modal when visibility=${visible}`, async () => {
          const { wrapper } = await render({ visibility: visible })
          expect(wrapper.find("Modal").prop("isOpen")).toEqual(visible)
          expect(wrapper.find("Modal").prop("toggle")).toEqual(
            toggleVisibilityStub,
          )
          if (visible) {
            expect(wrapper.find("ModalHeader").prop("toggle")).toEqual(
              toggleVisibilityStub,
            )
          }
        })
      })

      it("renders the date and url", async () => {
        const { wrapper } = await render()
        await simulateClickRadio(wrapper, idx)
        wrapper.update()
        expect(wrapper.find(".publish-option-description").text()).toContain(
          `Last updated: ${moment(website[publishDateField]).format(
            "dddd, MMMM D h:mma ZZ",
          )}`,
        )
        expect(wrapper.find(".publish-option-description a").prop("href")).toBe(
          website[urlField],
        )
        expect(
          wrapper.find(".publish-option-description a").prop("target"),
        ).toBe("_blank")
        expect(wrapper.find(".publish-option-description a").text()).toBe(
          website[urlField],
        )
      })

      it("renders the publish status", async () => {
        const { wrapper } = await render()
        await simulateClickRadio(wrapper, idx)
        wrapper.update()
        expect(wrapper.find("PublishStatusIndicator").prop("status")).toBe(
          website[publishStatusField],
        )
        expect(wrapper.find(".publish-option-description a").prop("href")).toBe(
          website[urlField],
        )
        expect(wrapper.find(".publish-option-description a").text()).toBe(
          website[urlField],
        )
      })

      it("renders a message if there is no date", async () => {
        website[publishDateField] = null
        const { wrapper } = await render()
        await simulateClickRadio(wrapper, idx)
        wrapper.update()
        expect(wrapper.find(".publish-option-description").text()).toContain(
          "Last updated: never published",
        )
      })

      it("has an option with the right label", async () => {
        const { wrapper } = await render()
        await simulateClickRadio(wrapper, idx)
        wrapper.update()
        expect(wrapper.find(".publish-option label").at(idx).text()).toBe(label)
      })

      it("disables the button if there is no unpublished content", async () => {
        website[unpublishedField] = false
        const { wrapper } = await render()
        await simulateClickPublish(wrapper, action)
        wrapper.update()
        expect(wrapper.find(".btn-publish").prop("disabled")).toBe(true)
      })

      it("disables publish button in production if no metadata is set", async () => {
        website[hasSiteMetaData] = false
        const { wrapper } = await render()
        await simulateClickPublish(wrapper, action)
        wrapper.update()
        action == "production" &&
          expect(wrapper.find(".btn-publish").prop("disabled")).toBe(true)
      })

      it("render only the preview button if user is not an admin", async () => {
        website["is_admin"] = false
        const { wrapper } = await render()
        expect(wrapper.find(`#publish-${action}`).exists()).toBe(
          action === "staging" ? true : false,
        )
      })

      it("renders a message about unpublished content", async () => {
        website[unpublishedField] = true
        const { wrapper } = await render()

        wrapper.update()
        expect(wrapper.find(".publish-option-description").text()).toContain(
          "You have unpublished changes.",
        )
      })
      ;[[], ["error 1", "error2"]].forEach((warnings) => {
        it(`${shouldIf(
          warnings && !isEmpty(warnings),
        )} render a warning about missing content`, async () => {
          website["content_warnings"] = warnings
          const { wrapper } = await render()
          const warningText = wrapper.find(".publish-warnings")
          expect(warningText.exists()).toBe(!isEmpty(warnings))
          warnings.forEach((warning) =>
            expect(warningText.text()).toContain(warning),
          )
        })
      })

      it("publish button sends the expected request", async () => {
        const actionStub = helper.mockPostRequest(
          siteApiActionUrl
            .param({
              name: website.name,
              action: api,
            })
            .toString(),
          {
            url_path: website.url_path,
          },
        )
        const { wrapper } = await render()
        await simulateClickPublish(wrapper, action)
        wrapper.update()
        website.has_site_metadata &&
          expect(
            wrapper.find("PublishForm").find(".btn-publish").prop("disabled"),
          ).toBeFalsy()
        await act(async () => {
          wrapper.find("PublishForm").find(".btn-publish").simulate("submit")
        })
        sinon.assert.calledOnceWithExactly(
          actionStub,
          `/api/websites/${website.name}/${api}/`,
          "POST",
          {
            body: {
              url_path: website.url_path,
            },
            headers: { "X-CSRFTOKEN": "" },
            credentials: undefined,
          },
        )
        sinon.assert.calledOnceWithExactly(
          refreshWebsiteStub,
          `/api/websites/${website.name}/`,
          "GET",
          {
            body: undefined,
            headers: undefined,
            credentials: undefined,
          },
        )
        sinon.assert.calledOnceWithExactly(toggleVisibilityStub)
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
    await act(() => user.click(envButton))

    const publishButton = await dom.findByText(dialog, "Publish")
    const form = dialog.querySelector("form")
    expect(form).toContainElement(publishButton)
    expect(publishButton).toHaveAttribute("type", "submit")
    assertInstanceOf(form, HTMLFormElement)

    setPublishResult(undefined, 500)
    act(() => form.submit())
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
    await act(() => user.click(envButton))

    const publishButton = await dom.findByText(dialog, "Publish")
    const form = dialog.querySelector("form")
    expect(form).toContainElement(publishButton)
    expect(publishButton).toHaveAttribute("type", "submit")
    assertInstanceOf(form, HTMLFormElement)

    setPublishResult({ url_path: "Some url error" }, 400)
    act(() => form.submit())

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
