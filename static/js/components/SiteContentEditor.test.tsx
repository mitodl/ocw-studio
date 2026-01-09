import { FormSchema } from "../types/forms"
import React from "react"
import { act, waitFor } from "@testing-library/react"
import * as yup from "yup"
import * as formikFuncs from "formik"
import sentryTestkit from "sentry-testkit"
import * as Sentry from "@sentry/react"

import SiteContentEditor, { SiteContentEditorProps } from "./SiteContentEditor"
import WebsiteContext from "../context/Website"

import * as siteContentFuncs from "../lib/site_content"
import {
  siteApiContentDetailUrl,
  siteApiContentUrl,
  siteApiDetailUrl,
} from "../lib/urls"
import { IntegrationTestHelper } from "../testing_utils"
import { screen } from "@testing-library/react"
import {
  makeRepeatableConfigItem,
  makeSingletonConfigItem,
  makeWebsiteContentDetail,
  makeWebsiteDetail,
  makeWebsiteStatus,
} from "../util/factories/websites"
import * as validationFuncs from "./forms/validation"
import { shouldIf } from "../test_util"

import {
  EditableConfigItem,
  Website,
  WebsiteContent,
  WebsiteContentModalState,
  WebsiteStatus,
} from "../types/websites"
import { contentDetailKey } from "../query-configs/websites"
import { createModalState } from "../types/modal_state"
import { FormikHelpers, FormikErrors, FormikValues } from "formik"
import { FormProps } from "./forms/SiteContentForm"

jest.mock("formik", () => {
  const formik = jest.requireActual("formik")
  return {
    __esModule: true,
    ...formik,
  }
})
jest.mock("../lib/site_content", () => {
  return {
    __esModule: true,
    ...jest.requireActual("../lib/site_content"),
  }
})

jest.mock("./forms/validation")
const getContentSchema = jest.mocked(validationFuncs.getContentSchema)

jest.mock("./widgets/MarkdownEditor", () => ({
  __esModule: true,
  default: jest.fn(() => <div>mock markdown editor</div>),
}))

interface CapturedFormProps extends FormProps {
  validate?: (values: FormikValues) => Promise<FormikErrors<any>>
}

let capturedFormProps: CapturedFormProps | null = null
const validateImpl: { fn: ((values: any) => Promise<any>) | null } = {
  fn: null,
}
const mockState = { shouldThrowError: null as Error | null }

jest.mock("./forms/SiteContentForm", () => ({
  __esModule: true,
  default: (props: FormProps) => {
    if (mockState.shouldThrowError) {
      throw mockState.shouldThrowError
    }
    const validate = async (values: any): Promise<any> => {
      if (validateImpl.fn) {
        return validateImpl.fn(values)
      }
      return {}
    }
    capturedFormProps = { ...props, validate }
    return <div data-testid="site-content-form">Mock Form</div>
  },
}))

const { testkit, sentryTransport } = sentryTestkit()
Sentry.init({
  dsn: "https://fake@fakesentry.example.com/123",
  transport: sentryTransport,
})

describe("SiteContent", () => {
  let helper: IntegrationTestHelper,
    website: Website,
    websiteStatus: WebsiteStatus,
    configItem: EditableConfigItem,
    formikStubs: Record<keyof FormikHelpers<any>, jest.Mock>,
    content: WebsiteContent,
    dismissStub: jest.Mock,
    fetchWebsiteListingStub: jest.Mock,
    successStubs: Record<string, jest.Mock>,
    mockContentSchema: FormSchema,
    setDirtyStub: jest.Mock

  beforeEach(() => {
    testkit.reset()
    capturedFormProps = null
    helper = new IntegrationTestHelper()
    website = makeWebsiteDetail()
    websiteStatus = makeWebsiteStatus(website)
    content = makeWebsiteContentDetail()
    configItem = makeRepeatableConfigItem()
    mockContentSchema = yup.object().shape({})
    getContentSchema.mockImplementation(() => mockContentSchema)
    dismissStub = jest.fn()
    fetchWebsiteListingStub = jest.fn()
    successStubs = {
      dismiss: dismissStub,
      fetchWebsiteContentListing: fetchWebsiteListingStub,
    }
    // @ts-expect-error There are others, e.g., setFieldError, but we do not need them
    formikStubs = {
      setErrors: jest.fn(),
      setSubmitting: jest.fn(),
      setStatus: jest.fn(),
    }
    setDirtyStub = jest.fn()

    helper.mockGetRequest(
      siteApiContentDetailUrl
        .param({ name: website.name, textId: content.text_id })
        .toString(),
      content,
    )

    helper.mockGetRequest(
      siteApiDetailUrl.param({ name: website.name }).toString(),
      website,
    )

    helper.mockGetRequest(
      siteApiDetailUrl
        .param({ name: website.name })
        .query({ only_status: true })
        .toString(),
      websiteStatus,
    )

    helper.mockPostRequest(
      siteApiContentUrl.param({ name: website.name }).toString(),
      {},
    )
  })

  afterEach(() => {
    jest.restoreAllMocks()
  })

  const renderComponent = async (
    props: Partial<SiteContentEditorProps> = {},
    initialContent: WebsiteContent | null = null,
  ) => {
    const defaultProps: SiteContentEditorProps = {
      configItem: configItem,
      loadContent: true,
      editorState: createModalState("adding"),
      setDirty: setDirtyStub,
    }
    const mergedProps = { ...defaultProps, ...props }

    const entities: Record<string, any> = {
      websiteDetails: {
        [website.name]: website,
      },
    }

    if (initialContent) {
      entities.websiteContentDetails = {
        [contentDetailKey({
          name: website.name,
          textId: initialContent.text_id,
        })]: initialContent,
      }
    }

    helper.patchInitialReduxState({ entities, queries: {} })

    const [result] = helper.render(
      <WebsiteContext.Provider value={website as Website}>
        <SiteContentEditor {...mergedProps} />
      </WebsiteContext.Provider>,
    )

    await waitFor(() => {
      expect(capturedFormProps).not.toBeNull()
    })

    return result
  }

  it("renders a form", async () => {
    await renderComponent()
    expect(screen.getByTestId("site-content-form")).toBeInTheDocument()
    expect(capturedFormProps).not.toBeNull()
    expect(capturedFormProps!.configItem).toStrictEqual(configItem)
    expect(capturedFormProps!.setDirty).toStrictEqual(setDirtyStub)
  })

  describe("validates using the content schema", () => {
    let validateYupSchemaStub: jest.SpyInstance,
      yupToFormErrorsStub: jest.SpyInstance,
      getContentSchemaStub: jest.SpyInstance

    beforeEach(() => {
      validateYupSchemaStub = jest.spyOn(formikFuncs, "validateYupSchema")
      yupToFormErrorsStub = jest.spyOn(formikFuncs, "yupToFormErrors")
      getContentSchemaStub = jest.spyOn(validationFuncs, "getContentSchema")
      getContentSchemaStub.mockReturnValue(mockContentSchema)

      validateImpl.fn = async (values: any): Promise<any> => {
        const schema = validationFuncs.getContentSchema(configItem, values)
        try {
          await formikFuncs.validateYupSchema(values, schema)
        } catch (e) {
          return formikFuncs.yupToFormErrors(e as yup.ValidationError)
        }
        return {}
      }
    })

    afterEach(() => {
      validateYupSchemaStub.mockRestore()
      yupToFormErrorsStub.mockRestore()
      getContentSchemaStub.mockRestore()
      validateImpl.fn = null
    })

    it("with no errors", async () => {
      await renderComponent()
      const values = { val: "ues" }
      const validate = capturedFormProps!.validate
      expect(validate).toBeDefined()
      const result = await validate!(values)
      expect(result).toStrictEqual({})
      expect(getContentSchemaStub).toHaveBeenCalledWith(configItem, values)
      expect(validateYupSchemaStub).toHaveBeenCalledWith(
        values,
        mockContentSchema,
      )
      expect(yupToFormErrorsStub).not.toHaveBeenCalled()
    })

    it("with some errors", async () => {
      await renderComponent()
      const values = { val: "ues" }
      const error = new Error("an error")
      validateYupSchemaStub.mockRejectedValue(error)
      const validationData = ["An error was found"]
      yupToFormErrorsStub.mockReturnValue(validationData)
      const validate = capturedFormProps!.validate
      expect(validate).toBeDefined()
      const result = await validate!(values)
      expect(result).toStrictEqual(validationData)
      expect(getContentSchemaStub).toHaveBeenCalledWith(configItem, values)
      expect(validateYupSchemaStub).toHaveBeenCalledWith(
        values,
        mockContentSchema,
      )
      expect(yupToFormErrorsStub).toHaveBeenCalledWith(error)
    })
  })

  //
  ;[
    [false, "for a repeatable config item"],
    [true, "for a singleton config item"],
  ].forEach(([isSingleton, desc]) => {
    it(`updates content via the form when creating new content ${desc}`, async () => {
      let expAddedPayload = {}
      let testConfigItem = configItem
      if (isSingleton) {
        testConfigItem = makeSingletonConfigItem(configItem.name)
        expAddedPayload = { text_id: testConfigItem.name }
      }
      await renderComponent({
        configItem: testConfigItem,
        ...successStubs,
      })
      const onSubmit = capturedFormProps!.onSubmit
      const values = {
        title: "A title",
        description: "Some description",
      }

      await act(async () => {
        await onSubmit(values, formikStubs as unknown as FormikHelpers<any>)
      })
      expect(helper.handleRequest).toHaveBeenCalledWith(
        siteApiContentUrl.param({ name: website.name }).toString(),
        "POST",
        {
          body: {
            type: testConfigItem.name,
            title: values.title,
            metadata: {
              description: values.description,
            },
            ...expAddedPayload,
          },
          headers: { "X-CSRFTOKEN": "" },
          credentials: undefined,
        },
      )

      expect(helper.handleRequest).toHaveBeenCalledWith(
        siteApiDetailUrl
          .param({ name: website.name })
          .query({ only_status: true })
          .toString(),
        "GET",
        {
          body: undefined,
          headers: undefined,
          credentials: undefined,
        },
      )

      expect(fetchWebsiteListingStub).toHaveBeenCalled()
      expect(dismissStub).toHaveBeenCalled()
    })
  })

  it("updates content via the form when editing existing content", async () => {
    helper.mockPatchRequest(
      siteApiContentDetailUrl
        .param({ name: website.name, textId: content.text_id })
        .toString(),
      content,
    )
    await renderComponent(
      {
        editorState: createModalState("editing", content.text_id),
        ...successStubs,
      },
      content,
    )

    const onSubmit = capturedFormProps!.onSubmit
    const values = {
      title: "A title",
      description: "Some description",
    }
    await act(async () => {
      await onSubmit(values, formikStubs as unknown as FormikHelpers<any>)
    })
    expect(helper.handleRequest).toHaveBeenCalledWith(
      siteApiContentDetailUrl
        .param({ name: website.name, textId: content.text_id })
        .toString(),
      "PATCH",
      {
        body: {
          title: values.title,
          metadata: {
            description: values.description,
          },
        },
        headers: { "X-CSRFTOKEN": "" },
        credentials: undefined,
      },
    )

    expect(helper.handleRequest).toHaveBeenCalledWith(
      siteApiDetailUrl
        .param({ name: website.name })
        .query({ only_status: true })
        .toString(),
      "GET",
      {
        body: undefined,
        headers: undefined,
        credentials: undefined,
      },
    )
    expect(fetchWebsiteListingStub).toHaveBeenCalled()
    expect(dismissStub).toHaveBeenCalled()
    expect(setDirtyStub).toHaveBeenCalledWith(false)
  })

  //
  ;["adding", "editing"].forEach((editorStateType) => {
    describe(`form validation for ${editorStateType}`, () => {
      let editorState: WebsiteContentModalState

      beforeEach(() => {
        editorState =
          editorStateType === "editing"
            ? createModalState("editing", content.text_id)
            : createModalState("adding")
        if (editorState.editing()) {
          helper.mockPatchRequest(
            siteApiContentDetailUrl
              .param({ name: website.name, textId: content.text_id })
              .toString(),
            { title: "uh oh" },
            500,
          )
        } else {
          helper.mockPostRequest(
            siteApiContentUrl.param({ name: website.name }).toString(),
            { title: "uh oh" },
            500,
          )
        }
      })

      it("handles field errors", async () => {
        const errorObj = { title: "uh oh" }
        await renderComponent(
          {
            editorState,
            ...successStubs,
          },
          editorState.editing() ? content : null,
        )

        const onSubmit = capturedFormProps!.onSubmit
        await act(async () => {
          await onSubmit({}, formikStubs as unknown as FormikHelpers<any>)
        })
        expect(formikStubs.setErrors).toHaveBeenCalledWith(errorObj)
      })

      it("handles non-field errors", async () => {
        const errorMessage = "uh oh"
        if (editorState.editing()) {
          helper.mockPatchRequest(
            siteApiContentDetailUrl
              .param({ name: website.name, textId: content.text_id })
              .toString(),
            errorMessage,
            500,
          )
        } else {
          helper.mockPostRequest(
            siteApiContentUrl.param({ name: website.name }).toString(),
            errorMessage,
            500,
          )
        }
        await renderComponent(
          { editorState, ...successStubs },
          editorState.editing() ? content : null,
        )

        const onSubmit = capturedFormProps!.onSubmit
        await act(async () => {
          await onSubmit({}, formikStubs as unknown as FormikHelpers<any>)
        })
        expect(formikStubs.setStatus).toHaveBeenCalledWith(errorMessage)
      })
    })
  })

  //
  ;[true, false].forEach((contentContext) => {
    describe(`with contentContext=${String(contentContext)}`, () => {
      let needsContentContextStub: jest.SpyInstance

      beforeEach(() => {
        needsContentContextStub = jest
          .spyOn(siteContentFuncs, "needsContentContext")
          .mockReturnValue(contentContext)
      })

      afterEach(() => {
        needsContentContextStub.mockRestore()
      })
      ;[
        [true, false, false, "content is passed in via props"],
        [true, true, false, "content is passed in and the loading flag=true"],
        [
          false,
          true,
          true,
          "content is not passed in and the loading flag=true",
        ],
      ].forEach(([hasContentProp, loadingFlag, shouldLoad, desc]) => {
        it(`${shouldIf(
          shouldLoad,
        )} load a content object if ${desc}`, async () => {
          helper.mockGetRequest(
            siteApiContentDetailUrl
              .param({ name: website.name, textId: content.text_id })
              .query(contentContext ? { content_context: true } : {})
              .toString(),
            content,
          )

          await renderComponent({
            editorState: createModalState("editing", content.text_id),
            loadContent: loadingFlag as boolean,
            ...(hasContentProp ? { content: content } : {}),
          })

          expect(screen.getByTestId("site-content-form")).toBeInTheDocument()
          expect(capturedFormProps!.content).toStrictEqual(content)
          if (shouldLoad) {
            expect(needsContentContextStub).toHaveBeenCalledWith(
              configItem.fields,
            )
          }
        })
      })
    })
  })

  it("only fetches content listing and hides modal if props are passed in", async () => {
    await renderComponent()

    const onSubmit = capturedFormProps!.onSubmit
    const values = {
      title: "A title",
      description: "Some description",
    }
    await act(async () => {
      await onSubmit(values, formikStubs as unknown as FormikHelpers<any>)
    })
    expect(helper.handleRequest).toHaveBeenCalledWith(
      siteApiContentUrl.param({ name: website.name }).toString(),
      "POST",
      {
        body: {
          type: configItem.name,
          title: values.title,
          metadata: {
            description: values.description,
          },
        },
        headers: { "X-CSRFTOKEN": "" },
        credentials: undefined,
      },
    )

    expect(fetchWebsiteListingStub).not.toHaveBeenCalled()
    expect(dismissStub).not.toHaveBeenCalled()
  })

  it("Displays a fallback for runtime errors and submits to sentry", () => {
    const consoleError = jest.spyOn(console, "error").mockImplementation(() => {
      // no-op
    })
    mockState.shouldThrowError = new Error("Ruh roh.")
    const configItemLocal = makeRepeatableConfigItem()
    const setDirty = jest.fn()
    const helperLocal = new IntegrationTestHelper()
    helperLocal.renderWithWebsite(
      <SiteContentEditor
        editorState={createModalState("adding")}
        loadContent={true}
        setDirty={setDirty}
        configItem={configItemLocal}
      />,
    )
    expect(testkit.reports()).toHaveLength(1)
    expect(testkit.reports()[0].error?.message).toBe("Ruh roh.")
    expect(consoleError).toHaveBeenCalled()
    screen.getByText("An error has occurred.", { exact: false })
    mockState.shouldThrowError = null
  })
})
