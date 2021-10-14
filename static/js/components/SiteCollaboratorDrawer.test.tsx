import sinon, { SinonStub } from "sinon"
import { act } from "react-dom/test-utils"

import SiteCollaboratorDrawer from "./SiteCollaboratorDrawer"
import { ROLE_EDITOR } from "../constants"
import IntegrationTestHelper, {
  TestRenderer
} from "../util/integration_test_helper"
import {
  makeWebsiteDetail,
  makeWebsiteCollaborator
} from "../util/factories/websites"
import {
  siteApiCollaboratorsDetailUrl,
  siteApiCollaboratorsUrl
} from "../lib/urls"

import { Website, WebsiteCollaborator } from "../types/websites"

describe("SiteCollaboratorDrawerTest", () => {
  let helper: IntegrationTestHelper,
    render: TestRenderer,
    website: Website,
    formikStubs: { [key: string]: SinonStub },
    editCollaboratorStub: SinonStub,
    addCollaboratorStub: SinonStub,
    toggleVisibilityStub: SinonStub,
    collaborator: WebsiteCollaborator

  const errorMsg = "Error"

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    website = makeWebsiteDetail()
    collaborator = makeWebsiteCollaborator()
    toggleVisibilityStub = sinon.stub()
    formikStubs = {
      setErrors:     sinon.stub(),
      setSubmitting: sinon.stub(),
      setStatus:     sinon.stub()
    }
    render = helper.configureRenderer(
      // @ts-ignore
      SiteCollaboratorDrawer,
      {
        collaborator:     null,
        visibility:       true,
        siteName:         website.name,
        toggleVisibility: toggleVisibilityStub
      },
      {
        entities: {
          collaborators: {
            [website.name]: [collaborator]
          }
        },
        queries: {}
      }
    )
    helper.handleRequestStub.returns({})
  })

  afterEach(() => {
    helper.cleanup()
  })

  describe("Edit an existing collaborator", () => {
    it("renders a form with the right props", async () => {
      const { wrapper } = await render({ collaborator })
      const form = wrapper.find("SiteCollaboratorForm")
      expect(form.exists()).toBe(true)
      expect(form.prop("onSubmit")).toBeDefined()
    })

    it("renders a modal header containing the collaborator email", async () => {
      const { wrapper } = await render({ collaborator })
      const header = wrapper.find("ModalHeader")
      expect(header.text()).toContain(`Edit ${collaborator.email}`)
    })

    it("edits a collaborator role and closes the dialog on success", async () => {
      editCollaboratorStub = helper.handleRequestStub
        .withArgs(
          siteApiCollaboratorsDetailUrl
            .param({
              name:   website.name,
              userId: collaborator.user_id
            })
            .toString(),
          "PATCH"
        )
        .returns({
          body:   collaborator,
          status: 201
        })
      const { wrapper } = await render({ collaborator })
      const form = wrapper.find("SiteCollaboratorForm")
      const onSubmit = form.prop("onSubmit")
      await act(async () => {
        // @ts-ignore
        onSubmit(
          {
            role: ROLE_EDITOR
          },
          // @ts-ignore
          formikStubs
        )
      })
      sinon.assert.calledOnce(editCollaboratorStub)
      sinon.assert.calledOnceWithExactly(formikStubs.setSubmitting, false)
      sinon.assert.calledOnce(toggleVisibilityStub)
    })

    it("sets form errors if the API request fails", async () => {
      const errorResp = {
        errors: {
          role: errorMsg
        }
      }
      editCollaboratorStub = helper.handleRequestStub
        .withArgs(
          siteApiCollaboratorsDetailUrl
            .param({
              name:   website.name,
              userId: collaborator.user_id
            })
            .toString(),

          "PATCH"
        )
        .returns({
          body:   errorResp,
          status: 400
        })
      const { wrapper } = await render({ collaborator })
      const form = wrapper.find("SiteCollaboratorForm")
      const onSubmit = form.prop("onSubmit")
      await act(async () => {
        // @ts-ignore
        onSubmit(
          {
            role: ROLE_EDITOR
          },
          // @ts-ignore
          formikStubs
        )
      })
      sinon.assert.calledOnce(editCollaboratorStub)
      sinon.assert.calledOnceWithExactly(formikStubs.setErrors, {
        ...errorResp.errors
      })
      sinon.assert.notCalled(toggleVisibilityStub)
    })

    it("sets form errors if the API request fails with a string error message", async () => {
      const errorResp = {
        errors: errorMsg
      }
      editCollaboratorStub = helper.handleRequestStub
        .withArgs(
          siteApiCollaboratorsDetailUrl
            .param({
              name:   website.name,
              userId: collaborator.user_id
            })
            .toString(),
          "PATCH"
        )
        .returns({
          body:   errorResp,
          status: 400
        })
      const { wrapper } = await render({ collaborator })
      const form = wrapper.find("SiteCollaboratorForm")
      const onSubmit = form.prop("onSubmit")
      await act(async () => {
        // @ts-ignore
        onSubmit(
          {
            role: ROLE_EDITOR
          },
          // @ts-ignore
          formikStubs
        )
      })
      sinon.assert.calledOnce(editCollaboratorStub)
      sinon.assert.calledOnceWithExactly(formikStubs.setStatus, errorMsg)
      sinon.assert.notCalled(toggleVisibilityStub)
    })
  })

  describe("Create a new collaborator", () => {
    it("renders a modal header containing expected text", async () => {
      const { wrapper } = await render()
      const header = wrapper.find("ModalHeader")
      expect(header.text()).toContain("Add collaborator")
    })

    it("creates a new collaborator", async () => {
      addCollaboratorStub = helper.handleRequestStub
        .withArgs(
          siteApiCollaboratorsUrl.param({ name: website.name }).toString(),
          "POST"
        )
        .returns({
          body:   makeWebsiteCollaborator(),
          status: 201
        })
      const { wrapper } = await render()
      const form = wrapper.find("SiteCollaboratorForm")
      const onSubmit = form.prop("onSubmit")
      await act(async () => {
        // @ts-ignore
        onSubmit(
          {
            email: "test@mit.edu",
            role:  ROLE_EDITOR
          },
          // @ts-ignore
          formikStubs
        )
      })
      sinon.assert.calledOnce(addCollaboratorStub)
      sinon.assert.calledOnceWithExactly(formikStubs.setSubmitting, false)
      sinon.assert.calledOnce(toggleVisibilityStub)
    })

    it("sets form errors if the API request fails", async () => {
      const errorResp = {
        errors: {
          email: errorMsg,
          role:  errorMsg
        }
      }
      addCollaboratorStub = helper.handleRequestStub
        .withArgs(
          siteApiCollaboratorsUrl.param({ name: website.name }).toString(),
          "POST"
        )
        .returns({
          body:   errorResp,
          status: 400
        })
      const { wrapper } = await render()
      const form = wrapper.find("SiteCollaboratorForm")
      const onSubmit = form.prop("onSubmit")
      await act(async () => {
        // @ts-ignore
        onSubmit(
          {
            email: "oops@mit.edu",
            role:  ROLE_EDITOR
          },
          // @ts-ignore
          formikStubs
        )
      })
      sinon.assert.calledOnce(addCollaboratorStub)
      sinon.assert.calledOnceWithExactly(formikStubs.setErrors, {
        ...errorResp.errors
      })
      sinon.assert.notCalled(toggleVisibilityStub)
    })

    it("sets form error if the API request fails with a string error message", async () => {
      const errorResp = {
        errors: errorMsg
      }
      addCollaboratorStub = helper.handleRequestStub
        .withArgs(
          siteApiCollaboratorsUrl.param({ name: website.name }).toString(),
          "POST"
        )
        .returns({
          body:   errorResp,
          status: 400
        })
      const { wrapper } = await render()
      const form = wrapper.find("SiteCollaboratorForm")
      const onSubmit = form.prop("onSubmit")
      await act(async () => {
        // @ts-ignore
        onSubmit(
          {
            email: "oops@mit.edu",
            role:  ROLE_EDITOR
          },
          // @ts-ignore
          formikStubs
        )
      })
      sinon.assert.calledOnce(addCollaboratorStub)
      sinon.assert.calledOnceWithExactly(formikStubs.setStatus, errorMsg)
      sinon.assert.notCalled(toggleVisibilityStub)
    })
  })
})
