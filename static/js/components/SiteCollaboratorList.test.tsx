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

  it("renders the collaborators list with expected number of items", async () => {
    const { wrapper } = await render()
    const numCollaborators = concat(collaborators, permanentAdmins).length
    const items = wrapper.find("li")
    expect(items.length).toBe(numCollaborators)
    // First collaborator in list should be editable
    expect(items.at(0).find("button.item-action-button").length).toBe(2)
    // Last collaborator in list should not be editable
    expect(
      items.at(numCollaborators - 1).find("button.item-action-button").length
    ).toBe(0)
  })

  it("the edit collaborator icon sets correct state and opens the modal", async () => {
    const { wrapper } = await render()
    const editLink = wrapper.find("button.item-action-button").at(0)

    act(() => {
      // @ts-ignore
      editLink.prop("onClick")({ preventDefault: helper.sandbox.stub() })
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
    const deleteIcon = wrapper.find("button.item-action-button").at(1)
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
