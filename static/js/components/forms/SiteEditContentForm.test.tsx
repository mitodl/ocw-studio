import React from "react"
import * as yup from "yup"
import sinon, { SinonSandbox, SinonStub } from "sinon"
import { shallow } from "enzyme"

import SiteEditContentForm from "./SiteEditContentForm"

import { defaultFormikChildProps } from "../../test_util"
import {
  makeWebsiteContentDetail,
  makeWebsiteConfigItem
} from "../../util/factories/websites"
jest.mock("../../lib/site_content")
import { componentFromWidget } from "../../lib/site_content"
jest.mock("./validation")
import { getContentSchema } from "./validation"

import { ConfigItem, WebsiteContent } from "../../types/websites"

describe("SiteEditContentForm", () => {
  let sandbox: SinonSandbox,
    onSubmitStub: SinonStub,
    setFieldValueStub: SinonStub,
    configItem: ConfigItem,
    content: WebsiteContent

  beforeEach(() => {
    sandbox = sinon.createSandbox()
    setFieldValueStub = sinon.stub()
    content = makeWebsiteContentDetail()
    configItem = makeWebsiteConfigItem(content.type)
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

    const form = renderInnerForm({ setFieldValue: setFieldValueStub })
    let idx = 0
    for (const field of configItem.fields) {
      const fieldWrapper = form.find("SiteContentField").at(idx)
      const setFieldValue =
        fieldWrapper.find("SiteContentField").prop("name") === "markdown" ?
          undefined :
          setFieldValueStub
      expect(fieldWrapper.find("SiteContentField").prop("field")).toBe(field)
      expect(fieldWrapper.find("SiteContentField").prop("field")).toBe(field)
      if (fieldWrapper.find("SiteContentField").prop("name") !== "markdown") {
        expect(
          fieldWrapper.find("SiteContentField").prop("setFieldValue")
        ).toBe(setFieldValue)
      }
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
