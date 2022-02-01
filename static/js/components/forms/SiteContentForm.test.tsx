import { times } from "ramda"
import React from "react"
import { Formik, Form } from "formik"
import sinon, { SinonSandbox, SinonStub } from "sinon"
import { shallow } from "enzyme"

import SiteContentForm from "./SiteContentForm"

import { defaultFormikChildProps, shouldIf } from "../../test_util"
import {
  makeEditableConfigItem,
  makeWebsiteConfigField,
  makeWebsiteContentDetail,
  makeWebsiteDetail
} from "../../util/factories/websites"
import * as siteContent from "../../lib/site_content"
import { useWebsite } from "../../context/Website"

import {
  EditableConfigItem,
  Website,
  WebsiteContent,
  WebsiteContentModalState,
  WidgetVariant
} from "../../types/websites"
import { FormSchema } from "../../types/forms"
import { createModalState } from "../../types/modal_state"
import * as domUtil from "../../util/dom"

jest.mock("../../lib/site_content")
jest.mock("../../context/Website")
jest.mock("../../util/dom")

const {
  componentFromWidget,
  contentInitialValues,
  fieldIsVisible,
  newInitialValues,
  renameNestedFields
} = siteContent as jest.Mocked<typeof siteContent>

const { scrollToElement } = domUtil as jest.Mocked<typeof domUtil>

describe("SiteContentForm", () => {
  let sandbox: SinonSandbox,
    onSubmitStub: SinonStub,
    configItem: EditableConfigItem,
    content: WebsiteContent,
    mockValidationSchema: FormSchema,
    website: Website,
    setDirtyStub: SinonStub

  beforeEach(() => {
    sandbox = sinon.createSandbox()
    content = makeWebsiteContentDetail()
    content.content_context = times(() => makeWebsiteContentDetail(), 3)
    configItem = makeEditableConfigItem(content.type)
    // @ts-ignore
    renameNestedFields.mockImplementation(() => [])
    website = makeWebsiteDetail()
    // @ts-ignore
    useWebsite.mockReturnValue(website)
    onSubmitStub = sandbox.stub()
    setDirtyStub = sandbox.stub()
  })

  afterEach(() => {
    sandbox.restore()
  })

  const renderForm = (props = {}) =>
    shallow(
      <SiteContentForm
        configItem={configItem}
        content={content}
        onSubmit={onSubmitStub}
        editorState={createModalState("adding")}
        setDirty={setDirtyStub}
        {...props}
      />
    )

  const renderInnerForm = (
    editorState: WebsiteContentModalState,
    formikChildProps: { [key: string]: any } = {}
  ) => {
    const wrapper = renderForm({ editorState })
    return (
      wrapper
        .find(Formik)
      // @ts-ignore
        .renderProp("children")({
          ...defaultFormikChildProps,
          ...formikChildProps
        })
    )
  }

  //
  ;[
    createModalState("adding") as WebsiteContentModalState,
    createModalState("editing", "id")
  ].forEach(editorState => {
    describe(editorState.state, () => {
      it("renders a form", () => {
        const widget = "fakeWidgetComponent"
        componentFromWidget.mockImplementation(() => widget)
        renameNestedFields.mockImplementation(() => configItem.fields)
        fieldIsVisible.mockImplementation(() => true)

        const form = renderInnerForm(editorState)
        let idx = 0
        for (const field of configItem.fields) {
          const fieldWrapper = form.find("SiteContentField").at(idx)
          expect(fieldWrapper.prop("field")).toBe(field)
          expect(fieldWrapper.prop("contentContext")).toBe(
            content.content_context
          )
          idx++
        }
      })

      it("displays a status", () => {
        const status = "testing status"
        const form = renderInnerForm(editorState, { status })
        expect(form.find(".form-error").text()).toBe(status)
      })

      //
      ;[true, false].forEach(isSubmitting => {
        it(`shows a button with disabled=${isSubmitting}`, () => {
          const form = renderInnerForm(editorState, { isSubmitting })
          expect(form.find("button[type='submit']").prop("disabled")).toBe(
            isSubmitting
          )
        })
      })

      it("has the correct Formik props", () => {
        // @ts-ignore
        const formik = renderForm({ editorState }).find("Formik")
        const validationSchema = formik.prop("validationSchema")
        expect(validationSchema).toStrictEqual(mockValidationSchema)
        expect(formik.prop("enableReinitialize")).toBe(true)
      })

      it("should pass an 'object' field to the ObjectField component", () => {
        const field = makeWebsiteConfigField({ widget: WidgetVariant.Object })
        configItem.fields = [field]
        // @ts-ignore
        fieldIsVisible.mockImplementation(() => true)
        // @ts-ignore
        renameNestedFields.mockImplementation(() => configItem.fields)
        const values = { some: "values" }
        const wrapper = renderInnerForm(editorState, { values })
        const objectWrapper = wrapper.find("ObjectField")
        expect(objectWrapper.exists()).toBeTruthy()
        expect(objectWrapper.prop("field")).toEqual(field)
        expect(objectWrapper.prop("contentContext")).toBe(
          content.content_context
        )
        expect(objectWrapper.prop("values")).toStrictEqual(values)
      })

      //
      ;[true, false].forEach(isGdriveEnabled => {
        [true, false].forEach(isResourceFileField => {
          it(`${shouldIf(
            !isResourceFileField || !isGdriveEnabled
          )} render file field if isResourceFileField=${String(
            isResourceFileField
          )} and isGdriveEnabled=${String(isGdriveEnabled)}`, () => {
            SETTINGS.gdrive_enabled = isGdriveEnabled
            content.type = isResourceFileField ? "resource" : "page"
            configItem = makeEditableConfigItem(content.type)
            const field = makeWebsiteConfigField({ widget: WidgetVariant.File })
            configItem.fields = [field]
            // @ts-ignore
            fieldIsVisible.mockImplementation(() => true)
            // @ts-ignore
            renameNestedFields.mockImplementation(() => configItem.fields)
            const values = { file: "courses/file.pdf" }
            const wrapper = renderInnerForm(editorState, { values })
            expect(wrapper.find("SiteContentField").exists()).toBe(
              !isResourceFileField || !isGdriveEnabled
            )
          })
        })
      })

      it("creates initialValues", () => {
        const newData = "new data",
          oldData = "old data"
        // @ts-ignore
        newInitialValues.mockReturnValue(newData)
        // @ts-ignore
        contentInitialValues.mockReturnValue(oldData)
        const wrapper = renderForm({ editorState })
        const initialValues = wrapper.find("Formik").prop("initialValues")
        if (editorState.adding()) {
          expect(initialValues).toBe(newData)
          expect(newInitialValues).toBeCalledWith(configItem.fields, website)
        } else {
          expect(initialValues).toBe(oldData)
          expect(contentInitialValues).toBeCalledWith(
            content,
            configItem.fields,
            website
          )
        }
      })

      //
      ;[true, false].forEach(isObjectField => {
        it(`passes an onChange prop for an ${
          isObjectField ? "object" : "non-object"
        } field which sets the dirty flag and calls handleChange for formik`, () => {
          const field = makeWebsiteConfigField({
            widget: isObjectField ? WidgetVariant.Object : WidgetVariant.String
          })
          configItem.fields = [field]
          // @ts-ignore
          fieldIsVisible.mockImplementation(() => true)
          // @ts-ignore
          renameNestedFields.mockImplementation(() => configItem.fields)
          const handleChangeStub = sandbox.stub()
          const form = renderInnerForm(editorState, {
            handleChange: handleChangeStub
          })
          const onChange = form
            .find(isObjectField ? "ObjectField" : "SiteContentField")
            .prop("onChange")
          const event: any = { preventDefault: sandbox.stub() }
          // @ts-ignore
          onChange(event)
          sinon.assert.calledOnceWithExactly(handleChangeStub, event)
          sinon.assert.calledOnceWithExactly(setDirtyStub, true)
        })
      })

      it("it scrolls to .form-error field", async () => {
        fieldIsVisible.mockImplementation(() => true)

        configItem = makeEditableConfigItem(content.type)
        configItem.fields.forEach(field => {
          field.required = true
        })

        expect(configItem.fields.map(f => f.name)).toEqual([
          "title",
          "description",
          "body"
        ])

        const wrapper = renderInnerForm(editorState, {
          values:       { title: "meow" },
          handleSubmit: jest.fn
        })
        const onSubmit = wrapper.find(Form).prop("onSubmit")!

        const formElement = document.createElement("form")

        const submitEvent = ({
          target: formElement
        } as unknown) as React.FormEvent<HTMLFormElement>
        await onSubmit(submitEvent)

        expect(scrollToElement).toHaveBeenCalledTimes(1)
        expect(scrollToElement).toHaveBeenCalledWith(formElement, ".form-error")
      })
    })
  })
})
