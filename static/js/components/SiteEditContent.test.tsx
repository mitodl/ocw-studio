const mockUseRouteMatch = jest.fn()

import { act } from "react-dom/test-utils"
import sinon, { SinonStub } from "sinon"

import SiteEditContent from "./SiteEditContent"

import { contentListingKey } from "../query-configs/websites"
import { siteApiContentDetailUrl } from "../lib/urls"
import IntegrationTestHelper, {
  TestRenderer
} from "../util/integration_test_helper"
import {
  makeWebsiteContentDetail,
  makeWebsiteDetail
} from "../util/factories/websites"

import { ConfigItem, Website, WebsiteContent } from "../types/websites"

jest.mock("react-router-dom", () => ({
  // @ts-ignore
  ...jest.requireActual("react-router-dom"),
  useRouteMatch: mockUseRouteMatch
}))
// ckeditor is not working properly in tests, but we don't need to test it here so just mock it away
jest.mock("./MarkdownEditor", () => "div")

describe("SiteEditContent", () => {
  let helper: IntegrationTestHelper,
    render: TestRenderer,
    website: Website,
    configItem: ConfigItem,
    historyPushStub: SinonStub,
    formikStubs: { [key: string]: SinonStub },
    content: WebsiteContent,
    toggleVisibilityStub: SinonStub

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    website = makeWebsiteDetail()
    content = makeWebsiteContentDetail()
    historyPushStub = helper.sandbox.stub()
    toggleVisibilityStub = helper.sandbox.stub()
    // @ts-ignore
    configItem = website.starter?.config?.collections.find(
      (item: ConfigItem) => item.name === "resource"
    )
    const params = { name: website.name, configname: configItem.name }
    mockUseRouteMatch.mockImplementation(() => ({
      params
    }))
    formikStubs = {
      setErrors:     helper.sandbox.stub(),
      setSubmitting: helper.sandbox.stub(),
      setStatus:     helper.sandbox.stub()
    }
    render = helper.configureRenderer(
      // @ts-ignore
      SiteEditContent,
      {
        history:          { push: historyPushStub },
        site:             website,
        configItem:       configItem,
        uuid:             content.uuid,
        visibility:       true,
        toggleVisibility: toggleVisibilityStub
      },
      {
        entities: {
          websiteDetails: {
            [website.name]: website
          },
          websiteContentListing: {
            [contentListingKey(website.name, configItem.name)]: [content]
          },
          websiteContentDetails: {
            [content.uuid]: content
          }
        },
        queries: {}
      }
    )
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("renders a form", async () => {
    const { wrapper } = await render()
    const form = wrapper.find("SiteEditForm")
    expect(form.exists()).toBe(true)
    expect(form.prop("configItem")).toBe(configItem)
  })

  it("submits content via the form", async () => {
    helper.handleRequestStub
      .withArgs(siteApiContentDetailUrl(website.name, content.uuid), "PATCH")
      .returns({
        body:   content,
        status: 200
      })
    const { wrapper } = await render()

    const onSubmit = wrapper.find("SiteEditForm").prop("onSubmit")
    const values = {
      title:       "A title",
      description: "Some description"
    }
    await act(async () => {
      // @ts-ignore
      await onSubmit(values, formikStubs)
    })
    sinon.assert.calledWith(
      helper.handleRequestStub,
      siteApiContentDetailUrl(website.name, content.uuid),
      "PATCH",
      {
        body: {
          title:    values.title,
          metadata: {
            description: values.description
          }
        },
        headers:     { "X-CSRFTOKEN": "" },
        credentials: undefined
      }
    )
  })

  it("handles field errors", async () => {
    const errorObj = { title: "uh oh" }
    helper.handleRequestStub
      .withArgs(siteApiContentDetailUrl(website.name, content.uuid), "PATCH")
      .returns({
        body:   errorObj,
        status: 500
      })
    const { wrapper } = await render()

    const onSubmit = wrapper.find("SiteEditForm").prop("onSubmit")
    await act(async () => {
      // @ts-ignore
      await onSubmit({}, formikStubs)
    })
    sinon.assert.calledWith(formikStubs.setErrors, errorObj)
  })

  it("handles non-field errors", async () => {
    const errorMessage = "uh oh"
    helper.handleRequestStub
      .withArgs(siteApiContentDetailUrl(website.name, content.uuid), "PATCH")
      .returns({
        body:   errorMessage,
        status: 500
      })
    const { wrapper } = await render()

    const onSubmit = wrapper.find("SiteEditForm").prop("onSubmit")
    await act(async () => {
      // @ts-ignore
      await onSubmit({}, formikStubs)
    })
    sinon.assert.calledWith(formikStubs.setStatus, errorMessage)
  })
})
