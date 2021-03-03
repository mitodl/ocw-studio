const mockUseRouteMatch = jest.fn()

import sinon, { SinonStub } from "sinon"
import { act } from "react-dom/test-utils"

import SiteCollaboratorAddPanel from "./SiteCollaboratorAddPanel"
import { ROLE_EDITOR } from "../constants"
import { siteCollaboratorsUrl } from "../lib/urls"
import IntegrationTestHelper, {
  TestRenderer
} from "../util/integration_test_helper"
import {
  makeWebsiteDetail,
  makeWebsiteCollaborator
} from "../util/factories/websites"

import { Website } from "../types/websites"

jest.mock("react-router-dom", () => ({
  // @ts-ignore
  ...jest.requireActual("react-router-dom"),
  useRouteMatch: mockUseRouteMatch
}))

describe("SiteCollaboratorAddPanel", () => {
  let helper: IntegrationTestHelper,
    render: TestRenderer,
    website: Website,
    historyPushStub: SinonStub,
    formikStubs: { [key: string]: SinonStub },
    createCollaboratorStub: SinonStub

  const errorMsg = "Error"

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    website = makeWebsiteDetail()
    historyPushStub = sinon.stub()
    const params = { name: website.name }
    mockUseRouteMatch.mockImplementation(() => ({
      params
    }))
    formikStubs = {
      setErrors:     sinon.stub(),
      setSubmitting: sinon.stub(),
      setStatus:     sinon.stub()
    }
    render = helper.configureRenderer(
      // @ts-ignore
      SiteCollaboratorAddPanel,
      {
        history: { push: historyPushStub }
      },
      {
        entities: {
          collaborators: {
            [website.name]: []
          }
        },
        queries: {}
      }
    )
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("renders a form with the right props", async () => {
    const { wrapper } = await render()
    const form = wrapper.find("SiteCollaboratorForm")
    expect(form.exists()).toBe(true)
    expect(form.prop("onSubmit")).toBeDefined()
  })

  it("creates a new collaborator and redirects on success", async () => {
    createCollaboratorStub = helper.handleRequestStub
      .withArgs(`/api/websites/${website.name}/collaborators/`, "POST")
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
    sinon.assert.calledOnce(createCollaboratorStub)
    sinon.assert.calledOnceWithExactly(formikStubs.setSubmitting, false)
    sinon.assert.calledOnceWithExactly(
      historyPushStub,
      siteCollaboratorsUrl(website.name)
    )
  })
  it("sets form errors if the API request fails", async () => {
    const errorResp = {
      errors: {
        email: errorMsg,
        role:  errorMsg
      }
    }
    createCollaboratorStub = helper.handleRequestStub
      .withArgs(`/api/websites/${website.name}/collaborators/`, "POST")
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
    sinon.assert.calledOnce(createCollaboratorStub)
    sinon.assert.calledOnceWithExactly(formikStubs.setErrors, {
      ...errorResp.errors
    })
    sinon.assert.notCalled(historyPushStub)
  })
  it("sets form error if the API request fails with a string error message", async () => {
    const errorResp = {
      errors: errorMsg
    }
    createCollaboratorStub = helper.handleRequestStub
      .withArgs(`/api/websites/${website.name}/collaborators/`, "POST")
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
    sinon.assert.calledOnce(createCollaboratorStub)
    sinon.assert.calledOnceWithExactly(formikStubs.setStatus, errorMsg)
    sinon.assert.notCalled(historyPushStub)
  })
})
