import { FormSchema } from "../types/forms"
import React from "react"
import { act } from "react-dom/test-utils"
import sinon, { SinonStub } from "sinon"
import * as yup from "yup"
import * as formikFuncs from "formik"

import SiteContentEditor from "./SiteContentEditor"
import WebsiteContext from "../context/Website"

import * as siteContentFuncs from "../lib/site_content"
import {
  siteApiContentDetailUrl,
  siteApiContentUrl,
  siteApiDetailUrl
} from "../lib/urls"
import IntegrationTestHelper, {
  TestRenderer
} from "../util/integration_test_helper"
import {
  makeRepeatableConfigItem,
  makeSingletonConfigItem,
  makeWebsiteContentDetail,
  makeWebsiteDetail,
  makeWebsiteStatus
} from "../util/factories/websites"
import { getContentSchema } from "./forms/validation"
import * as validationFuncs from "./forms/validation"
import { shouldIf } from "../test_util"

import {
  EditableConfigItem,
  Website,
  WebsiteContent,
  WebsiteContentModalState,
  WebsiteStatus
} from "../types/websites"
import { contentDetailKey } from "../query-configs/websites"
import { createModalState } from "../types/modal_state"
import {when} from "jest-when"

jest.mock("./forms/validation")

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
    websiteStatus: WebsiteStatus,
    configItem: EditableConfigItem,
    historyPushStub: SinonStub,
    formikStubs: { [key: string]: SinonStub },
    content: WebsiteContent,
    dismissStub: SinonStub,
    fetchWebsiteListingStub: SinonStub,
    successStubs: Record<string, SinonStub>,
    mockContentSchema: FormSchema,
    setDirtyStub: SinonStub

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    website = makeWebsiteDetail()
    websiteStatus = makeWebsiteStatus(website)
    content = makeWebsiteContentDetail()
    configItem = makeRepeatableConfigItem()
    mockContentSchema = yup.object().shape({})
    // @ts-ignore
    getContentSchema.mockImplementation(() => mockContentSchema)
    historyPushStub = helper.sandbox.stub()
    dismissStub = helper.sandbox.stub()
    fetchWebsiteListingStub = helper.sandbox.stub()
    successStubs = {
      dismiss:                    dismissStub,
      fetchWebsiteContentListing: fetchWebsiteListingStub
    }
    formikStubs = {
      setErrors:     helper.sandbox.stub(),
      setSubmitting: helper.sandbox.stub(),
      setStatus:     helper.sandbox.stub()
    }
    setDirtyStub = helper.sandbox.stub()

    helper.mockGetRequest(
      siteApiContentDetailUrl
        .param({ name: website.name, textId: content.text_id })
        .toString(),
      content
    )

    helper.mockGetRequest(
      siteApiDetailUrl.param({ name: website.name }).toString(),
      website
    )

    helper.mockGetRequest(
      siteApiDetailUrl
        .param({ name: website.name })
        .query({ only_status: true })
        .toString(),
      websiteStatus
    )

    helper.mockPostRequest(
      siteApiContentUrl.param({ name: website.name }).toString(),
      {}
    )

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
        configItem:  configItem,
        loadContent: true,
        editorState: createModalState("adding"),
        setDirty:    setDirtyStub
      },
      {
        entities: {
          websiteDetails: {
            [website.name]: website
          },
          websiteContentDetails: {
            [contentDetailKey({
              name:   website.name,
              textId: content.text_id
            })]: content
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
    expect(form.prop("configItem")).toStrictEqual(configItem)
    expect(form.prop("setDirty")).toStrictEqual(setDirtyStub)
  })

  describe("validates using the content schema", () => {
    let validateYupSchemaStub: SinonStub,
      yupToFormErrorsStub: SinonStub,
      getContentSchemaStub: SinonStub
    beforeEach(() => {
      validateYupSchemaStub = helper.sandbox.stub(
        formikFuncs,
        "validateYupSchema"
      )
      yupToFormErrorsStub = helper.sandbox.stub(formikFuncs, "yupToFormErrors")
      getContentSchemaStub = helper.sandbox.stub(
        validationFuncs,
        "getContentSchema"
      )
      getContentSchemaStub.returns(mockContentSchema)
    })

    it("with no errors", async () => {
      const { wrapper } = await render()
      const values = { val: "ues" }
      // @ts-ignore
      const result = await wrapper.find("Formik").prop("validate")(values)
      expect(result).toStrictEqual({})
      // @ts-ignore
      sinon.assert.calledOnceWithExactly(
        getContentSchemaStub,
        configItem,
        values
      )
      sinon.assert.calledOnceWithExactly(
        validateYupSchemaStub,
        values,
        mockContentSchema
      )
      sinon.assert.notCalled(yupToFormErrorsStub)
    })

    it("with some errors", async () => {
      const { wrapper } = await render()
      const values = { val: "ues" }
      const error = new Error("an error")
      validateYupSchemaStub.throws(error)
      const validationData = ["An error was found"]
      yupToFormErrorsStub.returns(validationData)
      // @ts-ignore
      const result = await wrapper.find("Formik").prop("validate")(values)
      expect(result).toStrictEqual(validationData)
      // @ts-ignore
      sinon.assert.calledOnceWithExactly(
        getContentSchemaStub,
        configItem,
        values
      )
      sinon.assert.calledOnceWithExactly(
        validateYupSchemaStub,
        values,
        mockContentSchema
      )
      sinon.assert.calledOnceWithExactly(yupToFormErrorsStub, error)
    })
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
      const { wrapper, store } = await render({
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
      await wrapper.update()
      expect(
        helper.handleRequestStub,
      ).toBeCalledWith(
        siteApiContentUrl.param({ name: website.name }).toString(),
        "POST",
        {
          body: {
            type:     configItem.name,
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

      expect(
        helper.handleRequestStub,
      ).toBeCalledWith(
        siteApiDetailUrl
          .param({ name: website.name })
          .query({ only_status: true })
          .toString(),
        "GET",
        {
          body:        undefined,
          headers:     undefined,
          credentials: undefined
        }
      )

      sinon.assert.called(fetchWebsiteListingStub)
      sinon.assert.called(dismissStub)
      const key = contentDetailKey({
        textId: content.text_id,
        name:   website.name
      })
      expect(
        store.getState().entities.websiteContentDetails[key]
      ).toStrictEqual(content)
    })
  })

  it("updates content via the form when editing existing content", async () => {
    helper.mockPatchRequest(
        siteApiContentDetailUrl
          .param({ name: website.name, textId: content.text_id })
          .toString(),
        content,
    )
    const { wrapper, store } = await render({
      editorState: createModalState("editing", content.text_id),
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
    expect(
      helper.handleRequestStub,
    ).toBeCalledWith(
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

    expect(
      helper.handleRequestStub,
    ).toBeCalledWith(
      siteApiDetailUrl
        .param({ name: website.name })
        .query({ only_status: true })
        .toString(),
      "GET",
      {
        body:        undefined,
        headers:     undefined,
        credentials: undefined
      }
    )
    sinon.assert.calledWith(fetchWebsiteListingStub)
    sinon.assert.calledWith(dismissStub)
    sinon.assert.calledWith(setDirtyStub, false)
    // @ts-ignore
    expect(store.getState().entities.websiteContentDetails).toStrictEqual({
      [contentDetailKey({
        textId: content.text_id,
        name:   website.name
      })]: content
    })
  })

  //
  ;["adding", "editing"].forEach(editorStateType => {
    describe(`form validation for ${editorStateType}`, () => {
      let url: string, method: string, editorState: WebsiteContentModalState

      beforeEach(() => {
        editorState =
          editorStateType === "editing" ?
            createModalState("editing", content.text_id) :
            createModalState("adding")
        if (editorState.editing()) {
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
        helper.mockGetRequest(url, errorObj, 500)

        const { wrapper } = await render({
          editorState,
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
        helper.mockGetRequest(url, errorMessage, 500)
        const { wrapper } = await render({ editorState, ...successStubs })

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
  ;[true, false].forEach(contentContext => {
    describe(`with contentContext=${String(contentContext)}`, () => {
      [
        [true, false, false, "content is passed in via props"],
        [true, true, false, "content is passed in and the loading flag=true"],
        [
          false,
          true,
          true,
          "content is not passed in and the loading flag=true"
        ]
      ].forEach(([hasContentProp, loadingFlag, shouldLoad, desc]) => {
        it(`${shouldIf(
          shouldLoad
        )} load a content object if ${desc}`, async () => {
          const needsContentContextStub = helper.sandbox
            .stub(siteContentFuncs, "needsContentContext")
            .returns(contentContext)
const url =              siteApiContentDetailUrl
                .param({ name: website.name, textId: content.text_id })
                .query(contentContext ? { content_context: true } : {})
                .toString()
          helper.mockGetRequest(
            url,
                content
            )

          const { wrapper } = await render({
            editorState: createModalState("editing", content.text_id),
            loadContent: loadingFlag,
            ...(hasContentProp ? { content: content } : {})
          })

          if (shouldLoad) {
            expect(helper.handleRequestStub).toHaveBeenCalledWith(
              url
            )
          } else {
            expect(helper.handleRequestStub).toHaveBeenCalledTimes(0)
          }

          const form = wrapper.find("SiteContentForm")
          expect(form.exists()).toBe(true)
          expect(form.prop("content")).toStrictEqual(content)
          if (shouldLoad) {
            sinon.assert.calledWith(needsContentContextStub, configItem.fields)
          }
        })
      })
    })
  })

  it("only fetches content listing and hides modal if props are passed in", async () => {
    const { wrapper } = await render()

    const onSubmit = wrapper.find("SiteContentForm").prop("onSubmit")
    const values = {
      title:       "A title",
      description: "Some description"
    }
    await act(async () => {
      // @ts-ignore
      await onSubmit(values, formikStubs)
    })
    expect(
      helper.handleRequestStub,
    ).toBeCalledWith(
      siteApiContentUrl.param({ name: website.name }).toString(),
      "POST",
      {
        body: {
          type:     configItem.name,
          title:    values.title,
          metadata: {
            description: values.description
          }
        },
        headers:     { "X-CSRFTOKEN": "" },
        credentials: undefined
      }
    )

    sinon.assert.notCalled(fetchWebsiteListingStub)
    sinon.assert.notCalled(dismissStub)
  })
})
