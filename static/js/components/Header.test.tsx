import { act } from "react-dom/test-utils"
import sinon from "sinon"
import useInterval from "@use-it/interval"

jest.mock("@use-it/interval", () => ({
  __esModule: true,
  default:    jest.fn()
}))

import Header from "./Header"
import IntegrationTestHelper, {
  TestRenderer
} from "../util/integration_test_helper"
import { logoutUrl, siteApiDetailUrl } from "../lib/urls"
import { makeWebsiteDetail } from "../util/factories/websites"
import { Website } from "../types/websites"
import { PublishStatuses } from "../constants"

describe("Header", () => {
  let helper: IntegrationTestHelper, render: TestRenderer

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    render = helper.configureRenderer(Header)
  })

  afterEach(() => {
    helper.cleanup()
    // @ts-ignore
    useInterval.mockClear()
  })

  it("includes the site logo and mit logo", async () => {
    const { wrapper } = await render()
    expect(
      wrapper
        .find("img")
        .at(0)
        .prop("src")
    ).toBe("/static/images/mit-logo.png")
    expect(
      wrapper
        .find("img")
        .at(1)
        .prop("src")
    ).toBe("/static/images/ocw-studio-logo.png")
  })

  it("shows the user's name and logout link for logged in users", async () => {
    const { wrapper } = await render()
    const links = wrapper.find(".links")
    expect(links.exists()).toBe(true)
    expect(links.find("span").text()).toBe("Jane Doe")
    const logoutLink = links.find("a")
    expect(logoutLink.text()).toBe("Log out")
    expect(logoutLink.prop("href")).toBe(logoutUrl.toString())
  })

  it("renders correctly for an anonymous user", async () => {
    SETTINGS.user = null
    const { wrapper } = await render()
    expect(wrapper.find(".links").exists()).toBe(false)
  })

  describe("with loaded website", () => {
    let website: Website

    beforeEach(() => {
      website = makeWebsiteDetail()

      render = helper.configureRenderer(
        Header,
        {},
        {
          entities: {
            websiteDetails: {
              [website.name]: website
            }
          },
          queries: {}
        }
      )

      helper.handleRequestStub
        .withArgs(
          siteApiDetailUrl
            .param({
              name: website.name
            })
            .query({ only_status: true })
            .toString(),
          "GET",
          {
            body:        undefined,
            headers:     undefined,
            credentials: undefined
          }
        )
        .returns({
          status: 200,
          body:   website
        })
    })

    it("shows the website title", async () => {
      const { wrapper } = await render({ website: website })
      expect(wrapper.find(".site-header h2").text()).toEqual(website.title)
    })

    it("toggles the publish drawer", async () => {
      const { wrapper } = await render({ website: website })
      expect(wrapper.find("PublishDrawer").prop("visibility")).toBeFalsy()
      act(() => {
        // @ts-ignore
        wrapper.find("PublishDrawer").prop("toggleVisibility")()
      })
      wrapper.update()
      expect(wrapper.find("PublishDrawer").prop("visibility")).toBeTruthy()
      act(() => {
        // @ts-ignore
        wrapper.find("PublishDrawer").prop("toggleVisibility")()
      })
      wrapper.update()
      expect(wrapper.find("PublishDrawer").prop("visibility")).toBeFalsy()
    })

    //
    ;[
      [PublishStatuses.PUBLISH_STATUS_SUCCEEDED, false],
      [PublishStatuses.PUBLISH_STATUS_ERRORED, false],
      [PublishStatuses.PUBLISH_STATUS_ABORTED, false],
      [PublishStatuses.PUBLISH_STATUS_PENDING, true],
      [PublishStatuses.PUBLISH_STATUS_NOT_STARTED, true]
    ].forEach(([status, shouldUpdate]) => {
      [
        ["draft_publish_status", "draft_publish_status_updated_on"],
        ["live_publish_status", "live_publish_status_updated_on"]
      ].forEach(([statusField, statusDateField]) => {
        describe("publish status", () => {
          beforeEach(() => {
            website = {
              ...website,
              live_publish_status:             PublishStatuses.PUBLISH_STATUS_ABORTED,
              draft_publish_status:            PublishStatuses.PUBLISH_STATUS_ABORTED,
              live_publish_status_updated_on:  "2020-01-01",
              draft_publish_status_updated_on: "2020-01-01",
              [statusField]:                   status,
              [statusDateField]:               "2021-01-01"
            }
          })

          it(`${
            shouldUpdate ? "polls" : "doesn't poll"
          } the website status when ${statusField}=${status}`, async () => {
            await render({ website })
            // @ts-ignore
            expect(useInterval).toBeCalledTimes(1)
            // @ts-ignore
            await useInterval.mock.calls[0][0]()

            const statusUrl = siteApiDetailUrl
              .param({ name: website.name })
              .query({ only_status: true })
              .toString()
            // @ts-ignore
            if (shouldUpdate) {
              sinon.assert.calledOnceWithExactly(
                helper.handleRequestStub,
                statusUrl,
                "GET",
                {
                  body:        undefined,
                  headers:     undefined,
                  credentials: undefined
                }
              )
            } else {
              sinon.assert.notCalled(helper.handleRequestStub)
            }
          })

          it("shows the right publish status", async () => {
            const { wrapper } = await render({ website })
            expect(wrapper.find("PublishStatusIndicator").prop("status")).toBe(
              status
            )
          })
        })
      })
    })
  })
})
