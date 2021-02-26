const mockUseRouteMatch = jest.fn()

import sinon, { SinonStub } from "sinon"
import { act } from "react-dom/test-utils"

import SitesDashboard from "./SitesDashboard"
import IntegrationTestHelper, {
  TestRenderer
} from "../util/integration_test_helper"
import {
  makeWebsiteDetail,
  makeWebsiteStarter
} from "../util/factories/websites"
import { siteUrl } from "../lib/urls"

import { Website, WebsiteStarter } from "../types/websites"

jest.mock("react-router-dom", () => ({
  // @ts-ignore
  ...jest.requireActual("react-router-dom"),
  useRouteMatch: mockUseRouteMatch
}))

describe("SitesDashboard", () => {
  let helper: IntegrationTestHelper,
    render: TestRenderer,
    starters: Array<WebsiteStarter>,
    website: Website,
    historyPushStub: SinonStub

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    starters = [makeWebsiteStarter(), makeWebsiteStarter()]
    website = makeWebsiteDetail()
    historyPushStub = sinon.stub()
    render = helper.configureRenderer(
      // @ts-ignore
      SitesDashboard,
      {
        history:  { push: historyPushStub },
        entities: {
          starters: []
        },
        queries: {}
      }
    )

    helper.handleRequestStub.withArgs(`/api/starters/`, "GET").returns({
      body:   starters,
      status: 200
    })
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("renders a form with the right props", async () => {
    const { wrapper } = await render()
    const form = wrapper.find("SiteForm")
    expect(form.exists()).toBe(true)
    expect(form.prop("websiteStarters")).toBe(starters)
  })

  describe("passes a form submit function", () => {
    const errorMsg = "Error"
    let formikStubs: { [key: string]: SinonStub }, createWebsiteStub: SinonStub

    beforeEach(() => {
      formikStubs = {
        setErrors:     sinon.stub(),
        setSubmitting: sinon.stub(),
        setStatus:     sinon.stub()
      }
    })

    it("that creates a new site and redirect on success", async () => {
      createWebsiteStub = helper.handleRequestStub
        .withArgs(`/api/websites/`, "POST")
        .returns({
          body:   website,
          status: 201
        })
      const { wrapper } = await render()
      const form = wrapper.find("SiteForm")
      const onSubmit = form.prop("onSubmit")
      await act(async () => {
        // @ts-ignore
        onSubmit(
          {
            title:   "My Title",
            starter: 1
          },
          // @ts-ignore
          formikStubs
        )
      })
      sinon.assert.calledOnce(createWebsiteStub)
      sinon.assert.calledOnceWithExactly(formikStubs.setSubmitting, false)
      sinon.assert.calledOnceWithExactly(historyPushStub, siteUrl(website.name))
    })
    it("that sets form errors if the API request fails", async () => {
      const errorResp = {
        errors: {
          title: errorMsg
        }
      }
      createWebsiteStub = helper.handleRequestStub
        .withArgs(`/api/websites/`, "POST")
        .returns({
          body:   errorResp,
          status: 400
        })
      const { wrapper } = await render()
      const form = wrapper.find("SiteForm")
      const onSubmit = form.prop("onSubmit")
      await act(async () => {
        // @ts-ignore
        onSubmit(
          {
            title:   errorMsg,
            starter: 1
          },
          // @ts-ignore
          formikStubs
        )
      })
      sinon.assert.calledOnce(createWebsiteStub)
      sinon.assert.calledOnceWithExactly(formikStubs.setErrors, {
        ...errorResp.errors,
        starter: undefined
      })
      sinon.assert.notCalled(historyPushStub)
    })
    it("that sets a status if the API request fails with a string error message", async () => {
      const errorResp = {
        errors: errorMsg
      }
      createWebsiteStub = helper.handleRequestStub
        .withArgs(`/api/websites/`, "POST")
        .returns({
          body:   errorResp,
          status: 400
        })
      const { wrapper } = await render()
      const form = wrapper.find("SiteForm")
      const onSubmit = form.prop("onSubmit")
      await act(async () => {
        // @ts-ignore
        onSubmit(
          {
            title:   "My Title",
            starter: 1
          },
          // @ts-ignore
          formikStubs
        )
      })
      sinon.assert.calledOnce(createWebsiteStub)
      sinon.assert.calledOnceWithExactly(formikStubs.setStatus, errorMsg)
      sinon.assert.notCalled(historyPushStub)
    })
  })
})
