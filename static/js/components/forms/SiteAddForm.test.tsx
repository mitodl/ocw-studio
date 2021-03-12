import React from "react"
import sinon, { SinonSandbox, SinonStub } from "sinon"
import { shallow } from "enzyme"

import SiteAddForm from "./SiteAddForm"

import { ConfigItem, Website } from "../../types/websites"
import { defaultFormikChildProps } from "../../test_util"
import { makeWebsite } from "../../util/factories/websites"
import { CONTENT_TYPE_PAGE } from "../../constants"

jest.mock("../../lib/site_content")
import { componentFromWidget } from "../../lib/site_content"

describe("SiteAddForm", () => {
  let sandbox: SinonSandbox,
    onSubmitStub: SinonStub,
    configItem: ConfigItem,
    website: Website

  beforeEach(() => {
    sandbox = sinon.createSandbox()
    website = makeWebsite()
    // @ts-ignore
    configItem = website.starter?.config?.collections.find(
      item => item.name === CONTENT_TYPE_PAGE
    )
  })

  afterEach(() => {
    sandbox.restore()
  })

  const renderForm = () =>
    shallow(<SiteAddForm configItem={configItem} onSubmit={onSubmitStub} />)

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

    const form = renderInnerForm()
    let idx = 0
    for (const fieldGroup of fieldGroups) {
      for (const field of fieldGroup) {
        const fieldWrapper = form.find("SiteContentField").at(idx)
        expect(fieldWrapper.find("SiteContentField").prop("field")).toBe(field)
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
})
