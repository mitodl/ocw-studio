import React from "react"
import sinon, { SinonStub } from "sinon"
import { shallow } from "enzyme"
import { ValidationError } from "yup"

import { SiteForm, websiteValidation } from "./SiteForm"
import { makeWebsiteStarter } from "../../util/factories/websites"
import { defaultFormikChildProps } from "../../test_util"

import { WebsiteStarter } from "../../types/websites"
import { Option } from "../widgets/SelectField"

describe("SiteForm", () => {
  let sandbox, onSubmitStub: SinonStub, websiteStarters: Array<WebsiteStarter>

  const renderForm = () =>
    shallow(
      <SiteForm onSubmit={onSubmitStub} websiteStarters={websiteStarters} />
    )

  const renderInnerForm = (formikChildProps: { [key: string]: any }) => {
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

  beforeEach(() => {
    sandbox = sinon.createSandbox()
    onSubmitStub = sandbox.stub()
    websiteStarters = [makeWebsiteStarter(), makeWebsiteStarter()]
  })

  it("passes onSubmit to Formik", () => {
    const wrapper = renderForm()

    const props = wrapper.find("Formik").props()
    expect(props.onSubmit).toBe(onSubmitStub)
    // @ts-ignore
    expect(props.validationSchema).toBe(websiteValidation)
  })

  it("shows an option for each website starter", () => {
    const form = renderInnerForm({ isSubmitting: false, status: "whatever" })
    const field = form
      .find("Field")
      .filterWhere(node => node.prop("name") === "starter")
    const options: Array<Option | string> = field.prop("options")
    expect(options).toHaveLength(websiteStarters.length)
    for (let i = 0; i < options.length; i++) {
      expect(options[i]["value"]).toBe(websiteStarters[i].id)
    }
  })

  describe("validation", () => {
    it("rejects an empty title", async () => {
      try {
        await expect(
          await websiteValidation.validateAt("title", { title: "" })
        ).rejects.toThrow()
      } catch (error) {
        expect(error).toBeInstanceOf(ValidationError)
        expect(error.errors).toStrictEqual(["Title is a required field"])
      }
    })
    it("rejects an empty name", async () => {
      try {
        await expect(
          await websiteValidation.validateAt("name", { name: "" })
        ).rejects.toThrow()
      } catch (error) {
        expect(error).toBeInstanceOf(ValidationError)
        expect(error.errors).toStrictEqual(["URL is a required field"])
      }
    })
    ;["这是我的", "Test", "test!", "test_test", "test()", "test_test"].forEach(
      name => {
        it("rejects an invalid name", async () => {
          try {
            await expect(
              await websiteValidation.validateAt("name", { name })
            ).rejects.toThrow()
          } catch (error) {
            expect(error).toBeInstanceOf(ValidationError)
            expect(error.errors).toStrictEqual([
              "Must be lowercase & only include letters (a-z), numbers, dashes"
            ])
          }
        })
      }
    )
  })
})
