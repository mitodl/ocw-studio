const mockUseRouteMatch = jest.fn()

import sinon, { SinonStub } from "sinon"
import { act } from "react-dom/test-utils"

import SiteCollaboratorEditPanel from "./SiteCollaboratorEditPanel"
import { ROLE_EDITOR } from "../constants"
import IntegrationTestHelper, {
  TestRenderer
} from "../util/integration_test_helper"
import {
  makeWebsite,
  makeWebsiteCollaborator
} from "../util/factories/websites"
import { siteCollaboratorsUrl } from "../lib/urls"

import { Website, WebsiteCollaborator } from "../types/websites"

jest.mock("react-router-dom", () => ({
  // @ts-ignore
  ...jest.requireActual("react-router-dom"),
  useRouteMatch: mockUseRouteMatch
}))

describe("SiteCollaboratorEditPanel", () => {
  let helper: IntegrationTestHelper,
    render: TestRenderer,
    website: Website,
    historyPushStub: SinonStub,
    formikStubs: { [key: string]: SinonStub },
    editCollaboratorStub: SinonStub,
    collaborator: WebsiteCollaborator

  const errorMsg = "Error"

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    website = makeWebsite()
    collaborator = makeWebsiteCollaborator()
    historyPushStub = sinon.stub()
    const params = { username: collaborator.username, name: website.name }
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
      SiteCollaboratorEditPanel,
      {
        history: { push: historyPushStub }
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
    helper.handleRequestStub
      .withArgs(`/api/websites/${website.name}/collaborators/`, "GET")
      .returns({
        body:   { results: [collaborator] },
        status: 200
      })
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

  it("edits a collaborator role and redirects on success", async () => {
    editCollaboratorStub = helper.handleRequestStub
      .withArgs(
        `/api/websites/${website.name}/collaborators/${collaborator.username}/`,
        "PATCH"
      )
      .returns({
        body:   collaborator,
        status: 201
      })
    const { wrapper } = await render()
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
    sinon.assert.calledOnceWithExactly(
      historyPushStub,
      siteCollaboratorsUrl(website.name)
    )
  })
  it("sets form errors if the API request fails", async () => {
    const errorResp = {
      errors: {
        role: errorMsg
      }
    }
    editCollaboratorStub = helper.handleRequestStub
      .withArgs(
        `/api/websites/${website.name}/collaborators/${collaborator.username}/`,
        "PATCH"
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
    sinon.assert.notCalled(historyPushStub)
  })
  it("sets form errors if the API request fails with a string error message", async () => {
    const errorResp = {
      errors: errorMsg
    }
    editCollaboratorStub = helper.handleRequestStub
      .withArgs(
        `/api/websites/${website.name}/collaborators/${collaborator.username}/`,
        "PATCH"
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
          role: ROLE_EDITOR
        },
        // @ts-ignore
        formikStubs
      )
    })
    sinon.assert.calledOnce(editCollaboratorStub)
    sinon.assert.calledOnceWithExactly(formikStubs.setStatus, errorMsg)
    sinon.assert.notCalled(historyPushStub)
  })
})
