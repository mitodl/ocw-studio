const mockUseRouteMatch = jest.fn()

import { act } from "react-dom/test-utils"
import { concat } from "ramda"
import sinon, { SinonStub } from "sinon"

import SiteCollaboratorList from "./SiteCollaboratorList"
import {
  siteCollaboratorsAddUrl,
  siteCollaboratorsDetailUrl,
  siteApiCollaboratorsUrl,
  siteApiCollaboratorsDetailUrl
} from "../lib/urls"
import {
  makePermanentWebsiteCollaborator,
  makeWebsiteDetail,
  makeWebsiteCollaborators
} from "../util/factories/websites"
import IntegrationTestHelper, {
  TestRenderer
} from "../util/integration_test_helper"

import { Website, WebsiteCollaborator } from "../types/websites"

jest.mock("react-router-dom", () => ({
  // @ts-ignore
  ...jest.requireActual("react-router-dom"),
  useRouteMatch: mockUseRouteMatch
}))

describe("SiteCollaboratorList", () => {
  let helper: IntegrationTestHelper,
    render: TestRenderer,
    website: Website,
    collaborators: WebsiteCollaborator[],
    permanentAdmins: WebsiteCollaborator[],
    deleteCollaboratorStub: SinonStub

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    website = makeWebsiteDetail()
    collaborators = makeWebsiteCollaborators()
    permanentAdmins = [makePermanentWebsiteCollaborator()]
    render = helper.configureRenderer(
      // @ts-ignore
      SiteCollaboratorList,
      {},
      {
        entities: {
          websites:      { website },
          collaborators: {
            [website.name]: concat(collaborators, permanentAdmins)
          }
        },
        queries: {}
      }
    )
    mockUseRouteMatch.mockImplementation(() => ({
      params: {
        name: website.name
      }
    }))
    helper.handleRequestStub
      .withArgs(
        siteApiCollaboratorsUrl.param({ name: website.name }).toString(),
        "GET"
      )
      .returns({
        body:   { results: concat(collaborators, permanentAdmins) },
        status: 200
      })
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("renders the collaborators list with expected number of rows in table", async () => {
    const { wrapper } = await render()
    const numCollaborators = concat(collaborators, permanentAdmins).length
    expect(wrapper.find("tr").length).toBe(numCollaborators)
    // First collaborator in list should be editable
    expect(
      wrapper
        .find("tr")
        .at(0)
        .find("i").length
    ).toBe(2)
    // Last collaborator in list should not be editable
    expect(
      wrapper
        .find("tr")
        .at(numCollaborators - 1)
        .find("i").length
    ).toBe(0)
  })

  it("the edit collaborator icon sends the user to the correct url", async () => {
    const { wrapper } = await render()
    const editLink = wrapper
      .find("tr")
      .at(0)
      .find(".edit-link")
      .at(0)
    expect(editLink.prop("to")).toBe(
      siteCollaboratorsDetailUrl
        .param({
          name:   website.name,
          userId: collaborators[0].user_id
        })
        .toString()
    )
  })

  it("the delete collaborator dialog works as expected", async () => {
    const collaborator = collaborators[0]
    const numCollaborators = concat(collaborators, permanentAdmins).length
    deleteCollaboratorStub = helper.handleRequestStub
      .withArgs(
        siteApiCollaboratorsDetailUrl
          .param({
            name:   website.name,
            userId: collaborator.user_id
          })
          .toString(),
        "DELETE"
      )
      .returns({
        status: 204
      })
    const { wrapper } = await render()
    const deleteIcon = wrapper
      .find("tr")
      .find("i")
      .at(1)
    act(() => {
      deleteIcon.simulate("click")
    })
    wrapper.update()
    const dialog = wrapper.find("Dialog")
    expect(dialog.prop("open")).toBe(true)
    expect(dialog.prop("bodyContent")).toContain(collaborators[0].name)
    act(() => {
      dialog
        .find("ModalFooter")
        .find("button")
        .at(0)
        .simulate("click")
    })
    wrapper.update()
    sinon.assert.calledOnce(deleteCollaboratorStub)
    expect(wrapper.find("tr").length).toBe(numCollaborators - 1)
  })

  it("the add collaborator button sends the user to the correct url", async () => {
    const { wrapper } = await render()
    expect(
      wrapper
        .find(".collaborator-add-btn")
        .at(0)
        .prop("to")
    ).toBe(siteCollaboratorsAddUrl.param({ name: website.name }).toString())
  })
})
