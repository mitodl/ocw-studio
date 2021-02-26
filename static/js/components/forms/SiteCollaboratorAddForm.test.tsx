import React from "react"
import sinon, { SinonStub } from "sinon"
import { shallow } from "enzyme"
import { ValidationError } from "yup"

import SiteCollaboratorAddForm, {
  collaboratorValidation
} from "./SiteCollaboratorAddForm"
import { defaultFormikChildProps } from "../../test_util"
import { EDITABLE_ROLES } from "../../constants"

describe("SiteCollaboratorAddForm", () => {
  let sandbox, onSubmitStub: SinonStub

  const renderForm = () =>
    shallow(<SiteCollaboratorAddForm onSubmit={onSubmitStub} />)

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
  })

  it("passes onSubmit to Formik", () => {
    const wrapper = renderForm()
    const props = wrapper.find("Formik").props()
    expect(props.onSubmit).toBe(onSubmitStub)
    // @ts-ignore
    expect(props.validationSchema).toBe(collaboratorValidation)
  })

  it("shows an option for each role, plus an empty option", () => {
    const form = renderInnerForm({ isSubmitting: false, status: "whatever" })
    const field = form
      .find("Field")
      .filterWhere(node => node.prop("name") === "role")
    const options = field.find("option")
    expect(options).toHaveLength(EDITABLE_ROLES.length + 1)
    expect(options.at(0).prop("value")).toBe("")
    for (let i = 1; i < options.length; i++) {
      expect(options.at(i).prop("value")).toBe(EDITABLE_ROLES[i - 1])
    }
  })

  it("shows an email field", () => {
    const form = renderInnerForm({ isSubmitting: false, status: "whatever" })
    expect(
      form.find("Field").filterWhere(node => node.prop("name") === "email")
    ).toHaveLength(1)
  })

  describe("validation", () => {
    it("rejects an empty role", async () => {
      try {
        await expect(
          await collaboratorValidation.validateAt("role", "")
        ).rejects.toThrow()
      } catch (error) {
        expect(error).toBeInstanceOf(ValidationError)
        expect(error.errors).toStrictEqual(["Role is a required field"])
      }
    })
    it("rejects an empty email", async () => {
      try {
        await expect(
          await collaboratorValidation.validateAt("email", { email: "" })
        ).rejects.toThrow()
      } catch (error) {
        expect(error).toBeInstanceOf(ValidationError)
        expect(error.errors).toStrictEqual(["Email is a required field"])
      }
    })
    it("rejects an invalid email", async () => {
      try {
        await expect(
          await collaboratorValidation.validateAt("email", {
            email: "mrbertrand.gmail.com"
          })
        ).rejects.toThrow()
      } catch (error) {
        expect(error).toBeInstanceOf(ValidationError)
        expect(error.errors).toStrictEqual(["Email must be a valid email"])
      }
    })
  })
})
