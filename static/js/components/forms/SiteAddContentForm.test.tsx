import React from "react"
import * as yup from "yup"
import sinon, { SinonSandbox, SinonStub } from "sinon"
import { shallow } from "enzyme"

import SiteAddContentForm from "./SiteAddContentForm"
import { defaultFormikChildProps } from "../../test_util"

jest.mock("../../lib/site_content")
import { componentFromWidget } from "../../lib/site_content"
jest.mock("./validation")
import { getContentSchema } from "./validation"

import { ConfigItem, WidgetVariant } from "../../types/websites"

describe("SiteAddContentForm", () => {
  let sandbox: SinonSandbox,
    onSubmitStub: SinonStub,
    setFieldValueStub: SinonStub,
    configItem: ConfigItem

  beforeEach(() => {
    sandbox = sinon.createSandbox()
    setFieldValueStub = sinon.stub()
    configItem = {
      fields: [
        {
          label:  "Title",
          name:   "title",
          widget: WidgetVariant.String
        },
        {
          label:  "Body",
          name:   "body",
          widget: WidgetVariant.Markdown
        }
      ],
      folder:   "content",
      label:    "Page",
      name:     "page",
      category: "Content"
    }
  })

  afterEach(() => {
    sandbox.restore()
  })

  const renderForm = () =>
    shallow(
      <SiteAddContentForm configItem={configItem} onSubmit={onSubmitStub} />
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

    const fieldGroups = [
      configItem.fields.filter(field => field.widget === "markdown"),
      configItem.fields.filter(field => field.widget !== "markdown")
    ]

    const form = renderInnerForm({ setFieldValue: setFieldValueStub })
    let idx = 0
    for (const fieldGroup of fieldGroups) {
      for (const field of fieldGroup) {
        const fieldWrapper = form.find("SiteContentField").at(idx)
        const setFieldValue =
          field.widget === "markdown" ? undefined : setFieldValueStub
        expect(fieldWrapper.find("SiteContentField").prop("field")).toBe(field)
        expect(
          fieldWrapper.find("SiteContentField").prop("setFieldValue")
        ).toBe(setFieldValue)
        idx++
      }
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
