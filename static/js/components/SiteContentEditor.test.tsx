import { ContentFormType } from "../types/forms"
import React from "react"
import { act } from "react-dom/test-utils"
import sinon, { SinonStub } from "sinon"

import SiteContentEditor from "./SiteContentEditor"

import { siteApiContentDetailUrl, siteApiContentUrl } from "../lib/urls"
import IntegrationTestHelper, {
  TestRenderer
} from "../util/integration_test_helper"
import {
  makeEditableConfigItem,
  makeWebsiteContentDetail,
  makeWebsiteDetail
} from "../util/factories/websites"

import { EditableConfigItem, Website, WebsiteContent } from "../types/websites"

const mockUseRouteMatch = jest.fn()

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

describe("SiteContent", () => {
  let helper: IntegrationTestHelper,
    render: TestRenderer,
    website: Website,
    configItem: EditableConfigItem,
    historyPushStub: SinonStub,
    formikStubs: { [key: string]: SinonStub },
    content: WebsiteContent,
    toggleVisibilityStub: SinonStub,
    routeParams: any,
    refreshStub: SinonStub

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    website = makeWebsiteDetail()
    content = makeWebsiteContentDetail()
    historyPushStub = helper.sandbox.stub()
    toggleVisibilityStub = helper.sandbox.stub()
    configItem = makeEditableConfigItem()
    routeParams = { name: website.name, contenttype: configItem.name }
    mockUseRouteMatch.mockImplementation(() => ({
      params: routeParams
    }))
    formikStubs = {
      setErrors:     helper.sandbox.stub(),
      setSubmitting: helper.sandbox.stub(),
      setStatus:     helper.sandbox.stub()
    }
    refreshStub = helper.sandbox.stub()
    render = helper.configureRenderer(
      // @ts-ignore
      SiteContentEditor,
      {
        history:                      { push: historyPushStub },
        site:                         website,
        configItem:                   configItem,
        uuid:                         content.uuid,
        visibility:                   true,
        toggleVisibility:             toggleVisibilityStub,
        contentType:                  routeParams.contenttype,
        websiteContentListingRequest: refreshStub
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
    const form = wrapper.find("SiteContentForm")
    expect(form.exists()).toBe(true)
    expect(form.prop("configItem")).toBe(configItem)
  })

  it("updates content via the form when creating new content", async () => {
    helper.handleRequestStub
      .withArgs(
        siteApiContentUrl.param({ name: website.name }).toString(),
        "POST"
      )
      .returns({
        body:   content,
        status: 200
      })
    const { wrapper } = await render({
      formType: ContentFormType.Add
    })

    const onSubmit = wrapper.find("SiteContentForm").prop("onSubmit")
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
      siteApiContentUrl.param({ name: website.name }).toString(),
      "POST",
      {
        body: {
          type:     routeParams.contenttype,
          title:    values.title,
          metadata: {
            description: values.description
          }
        },
        headers:     { "X-CSRFTOKEN": "" },
        credentials: undefined
      }
    )

    sinon.assert.calledWith(refreshStub)
    sinon.assert.calledWith(toggleVisibilityStub)
  })

  it("updates content via the form when editing existing content", async () => {
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
    const { wrapper } = await render({
      formType: ContentFormType.Edit
    })

    const onSubmit = wrapper.find("SiteContentForm").prop("onSubmit")
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

    sinon.assert.calledWith(refreshStub)
    sinon.assert.calledWith(toggleVisibilityStub)
  })

  //
  ;[ContentFormType.Edit, ContentFormType.Add].forEach(formType => {
    describe(`form validation for ${formType}`, () => {
      let url: string, method: string

      beforeEach(() => {
        if (formType === ContentFormType.Edit) {
          url = siteApiContentDetailUrl
            .param({ name: website.name, uuid: content.uuid })
            .toString()
          method = "PATCH"
        } else {
          url = siteApiContentUrl.param({ name: website.name }).toString()
          method = "POST"
        }
      })

      it("handles field errors", async () => {
        const errorObj = { title: "uh oh" }
        helper.handleRequestStub.withArgs(url, method).returns({
          body:   errorObj,
          status: 500
        })
        const { wrapper } = await render({
          formType
        })

        const onSubmit = wrapper.find("SiteContentForm").prop("onSubmit")
        await act(async () => {
          // @ts-ignore
          await onSubmit({}, formikStubs)
        })
        sinon.assert.calledWith(formikStubs.setErrors, errorObj)
      })

      it("handles non-field errors", async () => {
        const errorMessage = "uh oh"
        helper.handleRequestStub.withArgs(url, method).returns({
          body:   errorMessage,
          status: 500
        })
        const { wrapper } = await render({ formType })

        const onSubmit = wrapper.find("SiteContentForm").prop("onSubmit")
        await act(async () => {
          // @ts-ignore
          await onSubmit({}, formikStubs)
        })
        sinon.assert.calledWith(formikStubs.setStatus, errorMessage)
      })
    })
  })
})
