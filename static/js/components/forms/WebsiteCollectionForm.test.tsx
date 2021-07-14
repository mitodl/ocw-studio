import React from "react"
import sinon, { SinonStub } from "sinon"
import { mount } from "enzyme"

import { ErrorMessage } from "formik"

import { WebsiteCollectionFormSchema } from "./validation"
import WebsiteCollectionForm from "./WebsiteCollectionForm"
import { WebsiteCollectionFormFields, SubmitFunc } from "../../types/forms"

describe("WebsiteCollectionForm", () => {
  let sandbox: sinon.SinonSandbox,
    onSubmit: SinonStub<Parameters<SubmitFunc>, ReturnType<SubmitFunc>>,
    initialValues: WebsiteCollectionFormFields

  const renderWCForm = (props = {}) =>
    mount(
      <WebsiteCollectionForm
        onSubmit={onSubmit}
        initialValues={initialValues}
        {...props}
      />
    )

  beforeEach(() => {
    sandbox = sinon.createSandbox()
    onSubmit = sandbox.stub()
    initialValues = {
      title:       "",
      description: ""
    }
  })

  it("should pass the onSubmit prop down", () => {
    const wrapper = renderWCForm()
    expect(wrapper.find("Formik").prop("onSubmit")).toBe(onSubmit)
  })

  it("should set the validation", () => {
    const wrapper = renderWCForm()
    expect(wrapper.find("Formik").prop("validationSchema")).toBe(
      WebsiteCollectionFormSchema
    )
  })

  it("should set Field classname", () => {
    const wrapper = renderWCForm()
    wrapper.find("Field").forEach(field => {
      expect(field.prop("className")).toBe("form-control")
    })
  })

  it("should use initialValues", () => {
    const wrapper = renderWCForm({
      initialValues: {
        title:       "My Title",
        description: "My Description"
      }
    })

    expect(
      wrapper.find("Field").map(field => field.find("input").prop("value"))
    ).toEqual(["My Title", "My Description"])
  })

  it("should have ErrorMessage components", () => {
    const wrapper = renderWCForm()
    expect(
      wrapper.find(ErrorMessage).map(errorMsg => errorMsg.prop("name"))
    ).toEqual(["title", "description"])
  })
})
