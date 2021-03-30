const mockUseRouteMatch = jest.fn()

import sinon, { SinonStub } from "sinon"
import { act } from "react-dom/test-utils"

import SiteCollaboratorEditPanel from "./SiteCollaboratorEditPanel"
import { ROLE_EDITOR } from "../constants"
import IntegrationTestHelper, {
  TestRenderer
} from "../util/integration_test_helper"
import {
  makeWebsiteDetail,
  makeWebsiteCollaborator
} from "../util/factories/websites"
import {
  siteCollaboratorsUrl,
  siteApiCollaboratorsUrl,
  siteApiCollaboratorsDetailUrl
} from "../lib/urls"

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
    formikStubs: { [key: string]: SinonStub },
    editCollaboratorStub: SinonStub,
    collaborator: WebsiteCollaborator

  const errorMsg = "Error"

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    website = makeWebsiteDetail()
    collaborator = makeWebsiteCollaborator()
    const params = { userId: collaborator.user_id, name: website.name }
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
      {},
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
      .withArgs(
        siteApiCollaboratorsUrl.param({ name: website.name }).toString(),
        "GET"
      )
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
    expect(helper.browserHistory.location.pathname).toBe(
      siteCollaboratorsUrl.param({ name: website.name }).toString()
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
    expect(helper.browserHistory.location.pathname).toBe("/")
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
    expect(helper.browserHistory.location.pathname).toBe("/")
  })
})
