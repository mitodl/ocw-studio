import React from "react"
import { act } from "react-dom/test-utils"
import { concat } from "ramda"
import sinon, { SinonStub } from "sinon"

import SiteCollaboratorList from "./SiteCollaboratorList"
import {
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
import WebsiteContext from "../context/Website"

import { Website, WebsiteCollaborator } from "../types/websites"

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
      props => (
        <WebsiteContext.Provider value={website}>
          <SiteCollaboratorList {...props} />
        </WebsiteContext.Provider>
      ),
      {},
      {
        entities: {
          collaborators: {
            [website.name]: concat(collaborators, permanentAdmins)
          }
        },
        queries: {}
      }
    )
    helper.mockGetRequest(
      siteApiCollaboratorsUrl.param({ name: website.name }).toString(),
      { results: concat(collaborators, permanentAdmins) }
    )
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("sets the document title", async () => {
    const { wrapper } = await render()
    expect(wrapper.find("DocumentTitle").prop("title")).toBe(
      `OCW Studio | ${website.title} | Collaborators`
    )
  })

  it("renders the collaborators list with expected number of items", async () => {
    const { wrapper } = await render()
    const numCollaborators = concat(collaborators, permanentAdmins).length
    const items = wrapper.find("StudioListItem")
    expect(items.length).toBe(numCollaborators)
    // First collaborator in list should be editable
    expect(items.at(0).prop("menuOptions")).toHaveLength(2)
    // Last collaborator in list should not be editable
    expect(items.at(numCollaborators - 1).prop("menuOptions")).toHaveLength(0)
  })

  it("the edit collaborator icon sets correct state and opens the modal", async () => {
    const { wrapper } = await render()
    wrapper
      .find(".transparent-button")
      .at(0)
      .simulate("click")

    act(() => {
      // @ts-ignore
      wrapper
        .find("button.dropdown-item")
        .at(0)
        .simulate("click")
    })
    wrapper.update()
    const component = wrapper.find("SiteCollaboratorDrawer")
    expect(component.prop("collaborator")).toBe(collaborators[0])
    expect(component.prop("visibility")).toBe(true)

    act(() => {
      // @ts-ignore
      component.prop("toggleVisibility")()
    })
    wrapper.update()
    expect(wrapper.find("SiteCollaboratorDrawer").prop("visibility")).toBe(
      false
    )
  })

  it("the delete collaborator dialog works as expected", async () => {
    const collaborator = collaborators[0]
    const numCollaborators = concat(collaborators, permanentAdmins).length
    deleteCollaboratorStub = helper.mockDeleteRequest(
      siteApiCollaboratorsDetailUrl
        .param({
          name:   website.name,
          userId: collaborator.user_id
        })
        .toString(),
      {}
    )
    const { wrapper } = await render()
    wrapper
      .find(".transparent-button")
      .at(0)
      .simulate("click")
    wrapper.update()
    act(() => {
      wrapper
        .find("button.dropdown-item")
        .at(1)
        .simulate("click")
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
    expect(wrapper.find("li").length).toBe(numCollaborators - 1)
  })

  it("the add collaborator button sets correct state and opens the modal", async () => {
    const { wrapper } = await render()
    const addLink = wrapper.find("button").at(0)
    act(() => {
      // @ts-ignore
      addLink.prop("onClick")({ preventDefault: helper.sandbox.stub() })
    })
    wrapper.update()
    const component = wrapper.find("SiteCollaboratorDrawer")
    expect(component.prop("collaborator")).toBe(null)
    expect(component.prop("visibility")).toBe(true)

    act(() => {
      // @ts-ignore
      component.prop("toggleVisibility")()
    })
    wrapper.update()
    expect(wrapper.find("SiteCollaboratorDrawer").prop("visibility")).toBe(
      false
    )
  })
})
