const mockUseRouteMatch = jest.fn()

import React from "react"
import { act } from "react-dom/test-utils"
import sinon, { SinonStub } from "sinon"

import SiteEditContent from "./SiteEditContent"

import { siteApiContentDetailUrl } from "../lib/urls"
import IntegrationTestHelper, {
  TestRenderer
} from "../util/integration_test_helper"
import {
  makeWebsiteContentDetail,
  makeEditableConfigItem,
  makeWebsiteDetail
} from "../util/factories/websites"

import { EditableConfigItem, Website, WebsiteContent } from "../types/websites"

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

describe("SiteEditContent", () => {
  let helper: IntegrationTestHelper,
    render: TestRenderer,
    website: Website,
    configItem: EditableConfigItem,
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
    configItem = makeEditableConfigItem()
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
    const form = wrapper.find("SiteEditContentForm")
    expect(form.exists()).toBe(true)
    expect(form.prop("configItem")).toBe(configItem)
  })

  it("submits content via the form", async () => {
    helper.handleRequestStub
      .withArgs(
        siteApiContentDetailUrl
          .param({ name: website.name, uuid: content.uuid })
          .toString(),
        "PATCH"
      )
      .returns({
        body:   content,
        status: 200
      })
    const { wrapper } = await render()

    const onSubmit = wrapper.find("SiteEditContentForm").prop("onSubmit")
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
      siteApiContentDetailUrl
        .param({ name: website.name, uuid: content.uuid })
        .toString(),
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
      .withArgs(
        siteApiContentDetailUrl
          .param({ name: website.name, uuid: content.uuid })
          .toString(),
        "PATCH"
      )
      .returns({
        body:   errorObj,
        status: 500
      })
    const { wrapper } = await render()

    const onSubmit = wrapper.find("SiteEditContentForm").prop("onSubmit")
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
        siteApiContentDetailUrl
          .param({ name: website.name, uuid: content.uuid })
          .toString(),
        "PATCH"
      )
      .returns({
        body:   errorMessage,
        status: 500
      })
    const { wrapper } = await render()

    const onSubmit = wrapper.find("SiteEditContentForm").prop("onSubmit")
    await act(async () => {
      // @ts-ignore
      await onSubmit({}, formikStubs)
    })
    sinon.assert.calledWith(formikStubs.setStatus, errorMessage)
  })
})
