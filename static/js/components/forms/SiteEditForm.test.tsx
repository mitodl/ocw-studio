import React from "react"
import sinon, { SinonSandbox, SinonStub } from "sinon"
import { shallow } from "enzyme"
import { ErrorMessage } from "formik"

import SiteEditForm from "./SiteEditForm"

import { defaultFormikChildProps } from "../../test_util"
import {
  makeWebsiteContentDetail,
  makeWebsiteDetail
} from "../../util/factories/websites"
import { ConfigItem, Website, WebsiteContent } from "../../types/websites"

jest.mock("../../lib/site_content")
import { componentFromWidget } from "../../lib/site_content"

describe("SiteEditForm", () => {
  let sandbox: SinonSandbox,
    onSubmitStub: SinonStub,
    configItem: ConfigItem,
    content: WebsiteContent,
    website: Website

  beforeEach(() => {
    sandbox = sinon.createSandbox()
    website = makeWebsiteDetail()
    content = makeWebsiteContentDetail()
    // @ts-ignore
    configItem = website.starter?.config?.collections.find(
      item => item.name === content.type
    )
  })

  afterEach(() => {
    sandbox.restore()
  })

  const renderForm = () =>
    shallow(
      <SiteEditForm
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

    const form = renderInnerForm()
    let idx = 0
    for (const field of configItem.fields) {
      const group = form.find(".form-group").at(idx)

      const fieldWrapper = group.find("Field")
      expect(group.find("label").text()).toBe(field.label)
      expect(fieldWrapper.prop("as")).toBe(widget)
      expect(fieldWrapper.prop("name")).toBe(field.name)
      expect(group.find(ErrorMessage).prop("name")).toBe(field.name)
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
})
