import React from "react"
import sinon, { SinonStub } from "sinon"
import { shallow } from "enzyme"
import * as yup from "yup"

import SiteCollaboratorForm, {
  emailValidation,
  roleValidation
} from "./SiteCollaboratorForm"
import { EDITABLE_ROLES } from "../../constants"
import { defaultFormikChildProps } from "../../test_util"
import { makeWebsiteCollaborator } from "../../util/factories/websites"

import { WebsiteCollaborator } from "../../types/websites"
import { Option } from "../widgets/SelectField"

describe("SiteCollaboratorForm", () => {
  let sandbox,
    onSubmitStub: SinonStub,
    onCancelStub: SinonStub,
    collaborator: WebsiteCollaborator

  const renderForm = (collaborator: WebsiteCollaborator | null) =>
    shallow(
      <SiteCollaboratorForm
        collaborator={collaborator}
        onSubmit={onSubmitStub}
        onCancel={onCancelStub}
      />
    )

  const renderInnerForm = (
    formikChildProps: { [key: string]: any },
    collaborator: WebsiteCollaborator | null
  ) => {
    const wrapper = renderForm(collaborator)
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
    onCancelStub = sandbox.stub()
  })

  describe("add a new collaborator", () => {
    it("passes onSubmit to Formik", () => {
      const wrapper = renderForm(null)
      expect(wrapper.props().onSubmit).toBe(onSubmitStub)
      const props = wrapper.find("Formik").props()
      expect(props.onSubmit).toBe(onSubmitStub)
      // @ts-ignore
      expect(props.validationSchema.fields.role).toBeDefined()
      // @ts-ignore
      expect(props.validationSchema.fields.email).toBeDefined()
    })

    it("shows an option for each role, plus an empty option", () => {
      const form = renderInnerForm(
        { isSubmitting: false, status: "whatever" },
        null
      )
      const field = form
        .find("Field")
        .filterWhere(node => node.prop("name") === "role")
      const options: Array<Option> = field.prop("options")
      expect(options).toHaveLength(EDITABLE_ROLES.length + 1)
      for (let i = 1; i < options.length; i++) {
        expect(options[i]["value"]).toBe(EDITABLE_ROLES[i - 1])
      }
    })

    it("shows an email field", () => {
      const form = renderInnerForm(
        { isSubmitting: false, status: "whatever" },
        null
      )
      expect(
        form.find("Field").filterWhere(node => node.prop("name") === "email")
      ).toHaveLength(1)
    })
  })

  describe("edit an existing collaborator", () => {
    beforeEach(() => {
      collaborator = makeWebsiteCollaborator()
    })

    it("cancel button onClick function is onCancel prop", () => {
      const form = renderInnerForm(
        { isSubmitting: false, status: "whatever" },
        null
      )
      expect(
        form
          .find("button")
          .at(1)
          .prop("onClick")
      ).toBe(onCancelStub)
    })

    it("passes onSubmit to Formik", () => {
      const wrapper = renderForm(collaborator)
      const props = wrapper.find("Formik").props()
      expect(props.onSubmit).toBe(onSubmitStub)
      // @ts-ignore
      expect(props.validationSchema.fields.role).toBeDefined()
      // @ts-ignore
      expect(props.validationSchema.fields.email).toBeUndefined()
    })

    it("has current role selected", () => {
      const wrapper = renderForm(collaborator)
      const props = wrapper.find("Formik").props()
      //@ts-ignore
      expect(props.initialValues.role).toBe(collaborator.role)
    })

    it("shows an option for each role plus an empty choice", () => {
      const form = renderInnerForm(
        { isSubmitting: false, status: "whatever" },
        collaborator
      )
      const field = form
        .find("Field")
        .filterWhere(node => node.prop("name") === "role")
      const options: Array<Option> = field.prop("options")
      expect(options).toHaveLength(EDITABLE_ROLES.length + 1)
      for (let i = 1; i < options.length; i++) {
        expect(options[i]["value"]).toBe(EDITABLE_ROLES[i - 1])
      }
    })
  })

  describe("validation", () => {
    const collaboratorValidation = yup
      .object()
      .shape({ ...roleValidation, ...emailValidation })

    it("rejects an empty role", async () => {
      try {
        await expect(
          await collaboratorValidation.validateAt("role", "")
        ).rejects.toThrow()
      } catch (error) {
        expect(error).toBeInstanceOf(yup.ValidationError)
        expect(error.errors).toStrictEqual(["Role is a required field"])
      }
    })

    it("rejects an empty email", async () => {
      try {
        await expect(
          await collaboratorValidation.validateAt("email", { email: "" })
        ).rejects.toThrow()
      } catch (error) {
        expect(error).toBeInstanceOf(yup.ValidationError)
        expect(error.errors).toStrictEqual(["Email is a required field"])
      }
    })

    it("rejects an invalid email", async () => {
      try {
        await expect(
          await collaboratorValidation.validateAt("email", {
            email: "fake.test.com"
          })
        ).rejects.toThrow()
      } catch (error) {
        expect(error).toBeInstanceOf(yup.ValidationError)
        expect(error.errors).toStrictEqual(["Email must be a valid email"])
      }
    })

    it("does not reject a valid role", async () => {
      try {
        await expect(
          await collaboratorValidation.validateAt("role", "admin")
        ).rejects.toThrow()
      } catch (error) {
        expect(error).toBeInstanceOf(yup.ValidationError)
        expect(error.errors).toStrictEqual(["Role is a required field"])
      }
    })
  })
})
