import React from "react"
import * as yup from "yup"
import sinon, { SinonSandbox, SinonStub } from "sinon"
import { shallow } from "enzyme"

import SiteContentForm from "./SiteContentForm"

import { defaultFormikChildProps } from "../../test_util"
import {
  makeEditableConfigItem,
  makeWebsiteContentDetail
} from "../../util/factories/websites"
import {
  componentFromWidget,
  fieldIsVisible,
  splitFieldsIntoColumns
} from "../../lib/site_content"
import { getContentSchema } from "./validation"

import { EditableConfigItem, WebsiteContent } from "../../types/websites"
import { ContentFormType } from "../../types/forms"

jest.mock("../../lib/site_content")
jest.mock("./validation")

describe("SiteContentForm", () => {
  let sandbox: SinonSandbox,
    onSubmitStub: SinonStub,
    setFieldValueStub: SinonStub,
    configItem: EditableConfigItem,
    content: WebsiteContent

  beforeEach(() => {
    sandbox = sinon.createSandbox()
    setFieldValueStub = sinon.stub()
    content = makeWebsiteContentDetail()
    configItem = makeEditableConfigItem(content.type)
    // @ts-ignore
    splitFieldsIntoColumns.mockImplementation(() => [])
  })

  afterEach(() => {
    sandbox.restore()
  })

  const renderForm = (formType: ContentFormType) =>
    shallow(
      <SiteContentForm
        configItem={configItem}
        content={content}
        onSubmit={onSubmitStub}
        formType={formType}
      />
    )

  const renderInnerForm = (
    formType: ContentFormType,
    formikChildProps: { [key: string]: any } = {}
  ) => {
    const wrapper = renderForm(formType)
    return (
      wrapper
        .find("Formik")
      // @ts-ignore
        .renderProp("children")({
          ...defaultFormikChildProps,
          ...formikChildProps
        })
    )
  }

  //
  ;[ContentFormType.Add, ContentFormType.Edit].forEach(formType => {
    describe(formType, () => {
      it("renders a form", () => {
        const widget = "fakeWidgetComponent"
        // @ts-ignore
        componentFromWidget.mockImplementation(() => widget)
        // @ts-ignore
        fieldIsVisible.mockImplementation(() => true)
        // @ts-ignore
        splitFieldsIntoColumns.mockImplementation(() => [configItem.fields])

        const form = renderInnerForm(formType, {
          setFieldValue: setFieldValueStub
        })
        let idx = 0
        for (const field of configItem.fields) {
          const fieldWrapper = form.find("SiteContentField").at(idx)
          expect(fieldWrapper.prop("field")).toBe(field)
          expect(fieldWrapper.prop("setFieldValue")).toBe(setFieldValueStub)
          idx++
        }
      })

      it("displays a status", () => {
        const status = "testing status"
        const form = renderInnerForm(formType, { status })
        expect(form.find(".form-error").text()).toBe(status)
      })

      //
      ;[true, false].forEach(isSubmitting => {
        it(`shows a button with disabled=${isSubmitting}`, () => {
          const form = renderInnerForm(formType, { isSubmitting })
          expect(form.find("button[type='submit']").prop("disabled")).toBe(
            isSubmitting
          )
        })
      })

      it("has the correct Formik props", () => {
        const mockValidationSchema = yup.object().shape({})
        // @ts-ignore
        getContentSchema.mockReturnValueOnce(mockValidationSchema)
        // @ts-ignore
        splitFieldsIntoColumns.mockImplementation(() => [])
        const formik = renderForm(formType).find("Formik")
        const validationSchema = formik.prop("validationSchema")
        expect(validationSchema).toStrictEqual(mockValidationSchema)
        expect(formik.prop("enableReinitialize")).toBe(true)
      })
    })
  })
})
