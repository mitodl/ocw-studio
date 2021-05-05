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
  makeRepeatableConfigItem,
  makeSingletonConfigItem,
  makeWebsiteContentDetail,
  makeWebsiteDetail
} from "../util/factories/websites"

import { EditableConfigItem, Website, WebsiteContent } from "../types/websites"
import { shouldIf } from "../test_util"

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
    hideModalStub: SinonStub,
    routeParams: any,
    refreshStub: SinonStub,
    successStubs: Record<string, SinonStub>

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    website = makeWebsiteDetail()
    content = makeWebsiteContentDetail()
    configItem = makeRepeatableConfigItem()
    routeParams = { name: website.name, contenttype: configItem.name }
    mockUseRouteMatch.mockImplementation(() => ({
      params: routeParams
    }))
    historyPushStub = helper.sandbox.stub()
    hideModalStub = helper.sandbox.stub()
    refreshStub = helper.sandbox.stub()
    successStubs = {
      hideModal:                  hideModalStub,
      fetchWebsiteContentListing: refreshStub
    }
    formikStubs = {
      setErrors:     helper.sandbox.stub(),
      setSubmitting: helper.sandbox.stub(),
      setStatus:     helper.sandbox.stub()
    }
    render = helper.configureRenderer(
      // @ts-ignore
      SiteContentEditor,
      {
        history:     { push: historyPushStub },
        site:        website,
        textId:      content.text_id,
        configItem:  configItem,
        loadContent: true
      },
      {
        entities: {
          websiteDetails: {
            [website.name]: website
          },
          websiteContentDetails: {
            [content.text_id]: content
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

  //
  ;[
    [false, "for a repeatable config item"],
    [true, "for a singleton config item"]
  ].forEach(([isSingleton, desc]) => {
    it(`updates content via the form when creating new content ${desc}`, async () => {
      let expAddedPayload = {}
      if (isSingleton) {
        configItem = makeSingletonConfigItem(configItem.name)
        expAddedPayload = { text_id: configItem.name }
      }
      const { wrapper } = await render({
        formType:   ContentFormType.Add,
        textId:     null,
        configItem: configItem,
        ...successStubs
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
            },
            ...expAddedPayload
          },
          headers:     { "X-CSRFTOKEN": "" },
          credentials: undefined
        }
      )

      sinon.assert.calledWith(refreshStub)
      sinon.assert.calledWith(hideModalStub)
    })
  })

  it("updates content via the form when editing existing content", async () => {
    helper.handleRequestStub
      .withArgs(
        siteApiContentDetailUrl
          .param({ name: website.name, textId: content.text_id })
          .toString(),
        "PATCH"
      )
      .returns({
        body:   content,
        status: 200
      })
    const { wrapper } = await render({
      formType: ContentFormType.Edit,
      ...successStubs
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
        .param({ name: website.name, textId: content.text_id })
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
    sinon.assert.calledWith(hideModalStub)
  })

  //
  ;[ContentFormType.Edit, ContentFormType.Add].forEach(formType => {
    describe(`form validation for ${formType}`, () => {
      let url: string, method: string

      beforeEach(() => {
        if (formType === ContentFormType.Edit) {
          url = siteApiContentDetailUrl
            .param({ name: website.name, textId: content.text_id })
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
          formType,
          ...successStubs
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
        const { wrapper } = await render({ formType, ...successStubs })

        const onSubmit = wrapper.find("SiteContentForm").prop("onSubmit")
        await act(async () => {
          // @ts-ignore
          await onSubmit({}, formikStubs)
        })
        sinon.assert.calledWith(formikStubs.setStatus, errorMessage)
      })
    })
  })

  //
  ;[
    [true, false, false, "content is passed in via props"],
    [true, true, false, "content is passed in and the loading flag=true"],
    [false, true, true, "content is not passed in and the loading flag=true"]
  ].forEach(([hasContentProp, loadingFlag, shouldLoad, desc]) => {
    it(`${shouldIf(shouldLoad)} load a content object if ${desc}`, async () => {
      const contentDetailStub = helper.handleRequestStub
        .withArgs(
          siteApiContentDetailUrl
            .param({ name: website.name, textId: content.text_id })
            .toString(),
          "GET"
        )
        .returns({
          body:   content,
          status: 200
        })

      const { wrapper } = await render({
        formType:    ContentFormType.Edit,
        loadContent: loadingFlag,
        ...(hasContentProp ? { content: content } : {})
      })

      sinon.assert.callCount(contentDetailStub, shouldLoad ? 1 : 0)
      const form = wrapper.find("SiteContentForm")
      expect(form.exists()).toBe(true)
      expect(form.prop("content")).toStrictEqual(content)
    })
  })

  it("only fetches content listing and hides modal if props are passed in", async () => {
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

    sinon.assert.notCalled(refreshStub)
    sinon.assert.notCalled(hideModalStub)
  })
})
