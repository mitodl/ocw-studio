const mockUseRouteMatch = jest.fn()

import React from "react"
import { act } from "react-dom/test-utils"
import sinon, { SinonStub } from "sinon"

import SiteAddContent from "./SiteAddContent"

import { siteApiContentUrl } from "../lib/urls"
import IntegrationTestHelper, {
  TestRenderer
} from "../util/integration_test_helper"
import {
  makeWebsiteContentDetail,
  makeWebsiteDetail
} from "../util/factories/websites"

import { ConfigItem, Website } from "../types/websites"

jest.mock("react-router-dom", () => ({
  // @ts-ignore
  ...jest.requireActual("react-router-dom"),
  useRouteMatch: mockUseRouteMatch
}))

// ckeditor is not working properly in tests, but we don't need to test it here so just mock it away
function mocko() {
  return <div>mock</div>
}

jest.mock("./widgets/MarkdownEditor", () => ({
  __esModule: true,
  default:    mocko
}))

describe("SiteAddContent", () => {
  let helper: IntegrationTestHelper,
    render: TestRenderer,
    website: Website,
    configItem: ConfigItem,
    historyPushStub: SinonStub,
    formikStubs: { [key: string]: SinonStub }

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    website = makeWebsiteDetail()
    historyPushStub = helper.sandbox.stub()
    // @ts-ignore
    configItem = website.starter?.config?.collections.find(
      (item: ConfigItem) => item.name === "page"
    )
    const params = { name: website.name, contenttype: configItem.name }
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
      SiteAddContent,
      {
        history: { push: historyPushStub }
      },
      {
        entities: {
          websiteDetails: {
            [website.name]: website
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
    const form = wrapper.find("SiteAddContentForm")
    expect(form.exists()).toBe(true)
    expect(form.prop("configItem")).toBe(configItem)
  })

  it("submits content via the form", async () => {
    const content = makeWebsiteContentDetail()
    helper.handleRequestStub
      .withArgs(
        siteApiContentUrl.param({ name: website.name }).toString(),
        "POST"
      )
      .returns({
        body:   content,
        status: 201
      })
    const { wrapper } = await render()

    const onSubmit = wrapper.find("SiteAddContentForm").prop("onSubmit")
    const values = {
      title: "A title",
      body:  "some markdown here"
    }
    await act(async () => {
      // @ts-ignore
      await onSubmit(values, formikStubs)
    })
    sinon.assert.calledWith(
      helper.handleRequestStub,
      siteApiContentUrl.param({ name: website.name }).toString(),
      "POST",
      {
        body: {
          type:     configItem.name,
          title:    values.title,
          markdown: values.body
        },
        headers:     { "X-CSRFTOKEN": "" },
        credentials: undefined
      }
    )
  })

  it("handles field errors", async () => {
    const errorObj = { title: "uh oh" }
    helper.handleRequestStub
      .withArgs(
        siteApiContentUrl.param({ name: website.name }).toString(),
        "POST"
      )
      .returns({
        body:   errorObj,
        status: 500
      })
    const { wrapper } = await render()

    const onSubmit = wrapper.find("SiteAddContentForm").prop("onSubmit")
    await act(async () => {
      // @ts-ignore
      await onSubmit({}, formikStubs)
    })
    sinon.assert.calledWith(formikStubs.setErrors, errorObj)
  })

  it("handles non-field errors", async () => {
    const errorMessage = "uh oh"
    helper.handleRequestStub
      .withArgs(
        siteApiContentUrl.param({ name: website.name }).toString(),
        "POST"
      )
      .returns({
        body:   errorMessage,
        status: 500
      })
    const { wrapper } = await render()

    const onSubmit = wrapper.find("SiteAddContentForm").prop("onSubmit")
    await act(async () => {
      // @ts-ignore
      await onSubmit({}, formikStubs)
    })
    sinon.assert.calledWith(formikStubs.setStatus, errorMessage)
  })
})
