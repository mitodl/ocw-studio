import sinon, { SinonStub } from "sinon"
import { ReactWrapper } from "enzyme"
import { act } from "react-dom/test-utils"

import SiteCollaboratorDrawer from "./SiteCollaboratorDrawer"
import { ROLE_EDITOR } from "../constants"
import IntegrationTestHelper, {
  TestRenderer,
} from "../util/integration_test_helper_old"
import {
  makeWebsiteDetail,
  makeWebsiteCollaborator,
} from "../util/factories/websites"
import {
  siteApiCollaboratorsDetailUrl,
  siteApiCollaboratorsUrl,
} from "../lib/urls"

import {
  Website,
  WebsiteCollaborator,
  WebsiteCollaboratorFormData,
} from "../types/websites"
import {
  WebsiteCollaboratorListingResponse,
  collaboratorListingKey,
} from "../query-configs/websites"

const simulateClickSubmit = (
  wrapper: ReactWrapper,
  stubs: FormikStubs,
  data: WebsiteCollaboratorFormData,
) => {
  const onSubmit = wrapper.prop("onSubmit")
  if (typeof onSubmit !== "function") {
    throw new Error("onSubmit should be a function")
  }
  return act(async () => {
    onSubmit(data, stubs)
  })
}

type FormikStubs = Record<string, SinonStub>

describe("SiteCollaboratorDrawerTest", () => {
  let helper: IntegrationTestHelper,
    render: TestRenderer,
    website: Website,
    formikStubs: FormikStubs,
    editCollaboratorStub: SinonStub,
    addCollaboratorStub: SinonStub,
    toggleVisibilityStub: SinonStub,
    apiResponse: WebsiteCollaboratorListingResponse,
    collaborator: WebsiteCollaborator

  const errorMsg = "Error"

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    website = makeWebsiteDetail()
    collaborator = makeWebsiteCollaborator()
    toggleVisibilityStub = sinon.stub()
    formikStubs = {
      setErrors: sinon.stub(),
      setSubmitting: sinon.stub(),
      setStatus: sinon.stub(),
    }
    const listingParams = {
      name: website.name,
      offset: 0,
    }
    apiResponse = {
      results: [collaborator],
      count: 1,
      next: null,
      previous: null,
    }
    const collaboratorListingState = {
      [collaboratorListingKey(listingParams)]: {
        ...apiResponse,
        results: apiResponse.results.map(
          (collaborator) => collaborator.user_id,
        ),
      },
    }
    render = helper.configureRenderer(
      SiteCollaboratorDrawer,
      {
        collaborator: null,
        visibility: true,
        siteName: website.name,
        toggleVisibility: toggleVisibilityStub,
      },
      {
        entities: {
          collaborators: collaboratorListingState,
        },
        queries: {},
      },
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
      editCollaboratorStub = helper.mockPatchRequest(
        siteApiCollaboratorsDetailUrl
          .param({
            name: website.name,
            userId: collaborator.user_id,
          })
          .toString(),
        collaborator,
        201,
      )
      const { wrapper } = await render({ collaborator })
      const form = wrapper.find("SiteCollaboratorForm")

      await simulateClickSubmit(form, formikStubs, { role: ROLE_EDITOR })

      sinon.assert.calledOnce(editCollaboratorStub)
      sinon.assert.calledOnceWithExactly(formikStubs.setSubmitting, false)
      sinon.assert.calledOnce(toggleVisibilityStub)
    })

    it("sets form errors if the API request fails", async () => {
      const errorResp = {
        errors: {
          role: errorMsg,
        },
      }
      editCollaboratorStub = helper.mockPatchRequest(
        siteApiCollaboratorsDetailUrl
          .param({
            name: website.name,
            userId: collaborator.user_id,
          })
          .toString(),
        errorResp,
        400,
      )
      const { wrapper } = await render({ collaborator })
      const form = wrapper.find("SiteCollaboratorForm")

      await simulateClickSubmit(form, formikStubs, { role: ROLE_EDITOR })

      sinon.assert.calledOnce(editCollaboratorStub)
      sinon.assert.calledOnceWithExactly(formikStubs.setErrors, {
        ...errorResp.errors,
      })
      sinon.assert.notCalled(toggleVisibilityStub)
    })

    it("sets form errors if the API request fails with a string error message", async () => {
      const errorResp = {
        errors: errorMsg,
      }
      editCollaboratorStub = helper.mockPatchRequest(
        siteApiCollaboratorsDetailUrl
          .param({
            name: website.name,
            userId: collaborator.user_id,
          })
          .toString(),
        errorResp,
        400,
      )
      const { wrapper } = await render({ collaborator })
      const form = wrapper.find("SiteCollaboratorForm")
      await simulateClickSubmit(form, formikStubs, { role: ROLE_EDITOR })
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
      addCollaboratorStub = helper.mockPostRequest(
        siteApiCollaboratorsUrl.param({ name: website.name }).toString(),
        makeWebsiteCollaborator(),
      )
      const { wrapper } = await render()
      const form = wrapper.find("SiteCollaboratorForm")
      await simulateClickSubmit(form, formikStubs, {
        role: ROLE_EDITOR,
        email: "test@mit.edu",
      })
      sinon.assert.calledOnce(addCollaboratorStub)
      sinon.assert.calledOnceWithExactly(formikStubs.setSubmitting, false)
      sinon.assert.calledOnce(toggleVisibilityStub)
    })

    it("sets form errors if the API request fails", async () => {
      const errorResp = {
        errors: {
          email: errorMsg,
          role: errorMsg,
        },
      }
      addCollaboratorStub = helper.mockPostRequest(
        siteApiCollaboratorsUrl.param({ name: website.name }).toString(),
        errorResp,
        400,
      )
      const { wrapper } = await render()
      const form = wrapper.find("SiteCollaboratorForm")
      await simulateClickSubmit(form, formikStubs, {
        role: ROLE_EDITOR,
        email: "oops@mit.edu",
      })
      sinon.assert.calledOnce(addCollaboratorStub)
      sinon.assert.calledOnceWithExactly(formikStubs.setErrors, {
        ...errorResp.errors,
      })
      sinon.assert.notCalled(toggleVisibilityStub)
    })

    it("sets form error if the API request fails with a string error message", async () => {
      const errorResp = {
        errors: errorMsg,
      }
      addCollaboratorStub = helper.mockPostRequest(
        siteApiCollaboratorsUrl.param({ name: website.name }).toString(),
        errorResp,
        400,
      )
      const { wrapper } = await render()
      const form = wrapper.find("SiteCollaboratorForm")
      await simulateClickSubmit(form, formikStubs, {
        role: ROLE_EDITOR,
        email: "oops@mit.edu",
      })
      sinon.assert.calledOnce(addCollaboratorStub)
      sinon.assert.calledOnceWithExactly(formikStubs.setStatus, errorMsg)
      sinon.assert.notCalled(toggleVisibilityStub)
    })
  })
})
