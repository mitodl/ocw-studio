import React from "react"
import * as yup from "yup"
import sinon, { SinonSandbox, SinonStub } from "sinon"
import { shallow } from "enzyme"

import SiteEditContentForm from "./SiteEditContentForm"

import { defaultFormikChildProps } from "../../test_util"
import {
  makeWebsiteContentDetail,
  makeEditableConfigItem
} from "../../util/factories/websites"
jest.mock("../../lib/site_content")
import { componentFromWidget, fieldIsVisible } from "../../lib/site_content"
jest.mock("./validation")
import { getContentSchema } from "./validation"

import { EditableConfigItem, WebsiteContent } from "../../types/websites"

describe("SiteEditContentForm", () => {
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
  })

  afterEach(() => {
    sandbox.restore()
  })

  const renderForm = () =>
    shallow(
      <SiteEditContentForm
        configItem={configItem}
        content={content}
        onSubmit={onSubmitStub}
      />
    )

  const renderInnerForm = (formikChildProps: { [key: string]: any } = {}) => {
    const wrapper = renderForm()
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

  it("renders a form", () => {
    const widget = "fakeWidgetComponent"
    // @ts-ignore
    componentFromWidget.mockImplementation(() => widget)
    // @ts-ignore
    fieldIsVisible.mockImplementation(() => true)

    const form = renderInnerForm({ setFieldValue: setFieldValueStub })
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
    const form = renderInnerForm({ status })
    expect(form.find(".form-error").text()).toBe(status)
  })

  //
  ;[true, false].forEach(isSubmitting => {
    it(`shows a button with disabled=${isSubmitting}`, () => {
      const form = renderInnerForm({ isSubmitting })
      expect(form.find("button[type='submit']").prop("disabled")).toBe(
        isSubmitting
      )
    })
  })

  it("has the correct validation schema", () => {
    const mockValidationSchema = yup.object().shape({})
    // @ts-ignore
    getContentSchema.mockReturnValueOnce(mockValidationSchema)
    const formik = renderForm().find("Formik")
    const validationSchema = formik.prop("validationSchema")
    expect(validationSchema).toStrictEqual(mockValidationSchema)
  })
})
