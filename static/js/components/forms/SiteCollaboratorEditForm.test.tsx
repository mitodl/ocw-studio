import React from "react"
import sinon, { SinonStub } from "sinon"
import { shallow } from "enzyme"
import { ValidationError } from "yup"
import { makeWebsiteCollaborator } from "../../util/factories/websites"
import SiteCollaboratorEditForm, {
  collaboratorValidation
} from "./SiteCollaboratorEditForm"
import { defaultFormikChildProps } from "../../test_util"
import { EDITABLE_ROLES } from "../../constants"
import { WebsiteCollaborator } from "../../types/websites"

describe("SiteCollaboratorEditForm", () => {
  let sandbox, onSubmitStub: SinonStub, collaborator: WebsiteCollaborator

  const renderForm = () =>
    shallow(
      <SiteCollaboratorEditForm
        onSubmit={onSubmitStub}
        collaborator={collaborator}
      />
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
    collaborator = makeWebsiteCollaborator()
  })

  it("passes onSubmit to Formik", () => {
    const wrapper = renderForm()
    const props = wrapper.find("Formik").props()
    expect(props.onSubmit).toBe(onSubmitStub)
    // @ts-ignore
    expect(props.validationSchema).toBe(collaboratorValidation)
  })

  it("has current role selected", () => {
    const wrapper = renderForm()
    const props = wrapper.find("Formik").props()
    //@ts-ignore
    expect(props.initialValues.role).toBe(collaborator.role)
  })

  it("shows an option for each role plus an empty choice", () => {
    const form = renderInnerForm({ isSubmitting: false, status: "whatever" })
    const field = form
      .find("Field")
      .filterWhere(node => node.prop("name") === "role")
    const options = field.find("option")
    expect(options).toHaveLength(EDITABLE_ROLES.length + 1)
    for (let i = 1; i < options.length; i++) {
      expect(options.at(i).prop("value")).toBe(EDITABLE_ROLES[i - 1])
    }
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

    it("does not reject an valid role", async () => {
      try {
        await expect(
          await collaboratorValidation.validateAt("role", "admin")
        ).rejects.toThrow()
      } catch (error) {
        expect(error).toBeInstanceOf(ValidationError)
        expect(error.errors).toStrictEqual(["Role is a required field"])
      }
    })
  })
})
