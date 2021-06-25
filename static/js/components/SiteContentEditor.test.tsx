import { ContentFormType, FormSchema } from "../types/forms"
import React from "react"
import { act } from "react-dom/test-utils"
import sinon, { SinonStub } from "sinon"
import * as yup from "yup"

import SiteContentEditor from "./SiteContentEditor"
import WebsiteContext from "../context/Website"

import { siteApiContentDetailUrl, siteApiContentUrl } from "../lib/urls"
import IntegrationTestHelper, {
  TestRenderer
} from "../util/integration_test_helper"
import {
  makeRepeatableConfigItem,
  makeSingletonConfigItem,
  makeWebsiteConfigField,
  makeWebsiteContentDetail,
  makeWebsiteDetail
} from "../util/factories/websites"
import { getContentSchema } from "./forms/validation"
import { shouldIf } from "../test_util"

import {
  EditableConfigItem,
  Website,
  WebsiteContent,
  WidgetVariant
} from "../types/websites"
import { DEFAULT_TITLE_FIELD } from "../lib/site_content"

jest.mock("./forms/validation")

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
    successStubs: Record<string, SinonStub>,
    mockContentSchema: FormSchema

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    website = makeWebsiteDetail()
    content = makeWebsiteContentDetail()
    configItem = makeRepeatableConfigItem()
    routeParams = { name: website.name, contenttype: configItem.name }
    mockUseRouteMatch.mockImplementation(() => ({
      params: routeParams
    }))
    mockContentSchema = yup.object().shape({})
    // @ts-ignore
    getContentSchema.mockImplementation(() => mockContentSchema)
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
      function(props) {
        return (
          <WebsiteContext.Provider value={website as Website}>
            <SiteContentEditor {...props} />
          </WebsiteContext.Provider>
        )
      },
      {
        history:     { push: historyPushStub },
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
    expect(form.prop("fields")).toStrictEqual(configItem.fields)
    expect(form.prop("schema")).toStrictEqual(mockContentSchema)
  })

  it("modifies config item fields before passing them on to form component", async () => {
    const objectField = makeWebsiteConfigField({
      widget: WidgetVariant.Object,
      label:  "myobject",
      fields: [
        makeWebsiteConfigField({
          widget: WidgetVariant.String,
          label:  "mystring"
        })
      ]
    })
    const { wrapper } = await render({
      configItem: {
        ...makeRepeatableConfigItem(),
        fields: [objectField]
      }
    })
    const form = wrapper.find("SiteContentForm")
    expect(form.prop("fields")).toStrictEqual([
      // Title field should be added by default
      DEFAULT_TITLE_FIELD,
      // Nested object field should be not renamed
      objectField
    ])
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
