import React from "react"
import { act } from "react-dom/test-utils"
import { concat } from "ramda"
import sinon, { SinonStub } from "sinon"

import SiteCollaboratorList from "./SiteCollaboratorList"
import {
  siteApiCollaboratorsUrl,
  siteApiCollaboratorsDetailUrl,
} from "../lib/urls"
import {
  makePermanentWebsiteCollaborator,
  makeWebsiteDetail,
  makeWebsiteCollaborators,
} from "../util/factories/websites"
import IntegrationTestHelper, {
  TestRenderer,
} from "../util/integration_test_helper_old"
import WebsiteContext from "../context/Website"

import { Website, WebsiteCollaborator } from "../types/websites"
import SiteCollaboratorDrawer from "./SiteCollaboratorDrawer"
import { WebsiteCollaboratorListingResponse, collaboratorDetailKey, collaboratorListingKey } from "../query-configs/websites"
import { StudioListItem } from "./StudioList"

describe("SiteCollaboratorList", () => {
  let helper: IntegrationTestHelper,
    render: TestRenderer,
    website: Website,
    collaborators: WebsiteCollaborator[],
    permanentAdmin: WebsiteCollaborator[],
    deleteCollaboratorStub: SinonStub,
    apiResponse: WebsiteCollaboratorListingResponse,
    websiteCollaboratorDetailsLookup: Record<string, WebsiteCollaborator>


  beforeEach(() => {
    helper = new IntegrationTestHelper()
    website = makeWebsiteDetail()
    collaborators = makeWebsiteCollaborators()
    permanentAdmin = [makePermanentWebsiteCollaborator()]
    collaborators = concat(collaborators, permanentAdmin)
    websiteCollaboratorDetailsLookup = {}
    console.log
    for (const collaborator of collaborators) {
      websiteCollaboratorDetailsLookup[
        collaboratorDetailKey({ name: website.name, userId: collaborator.user_id })
      ] = collaborator
    }
    console.log("collab=",collaborators )

    const listingParams = {
      name:   website.name,
      offset: 0
    }
    apiResponse = {
      results:  collaborators,
      count:    6,
      next:     null,
      previous: null
    }
    const collaboratorListingLookup = {
      [collaboratorListingKey(listingParams)]: {
        ...apiResponse,
        results: apiResponse.results.map(item => item.user_id)
      }
    }
    helper.mockGetRequest(
      siteApiCollaboratorsUrl
        .param({
          name: website.name
        })
        .query({ offset: 0 })
        .toString(),
      apiResponse
    )
    render = helper.configureRenderer(
      (props) => (
        <WebsiteContext.Provider value={website}>
          <SiteCollaboratorList {...props} />
        </WebsiteContext.Provider>
      ),
      {},
      {
        entities: {
          collaborators: collaboratorListingLookup,
          websiteCollaboratorDetails: websiteCollaboratorDetailsLookup
        },
        queries: {},
      },
    )
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("sets the document title", async () => {
    const { wrapper } = await render()
    expect(wrapper.find("DocumentTitle").prop("title")).toBe(
      `OCW Studio | ${website.title} | Collaborators`,
    )
  })

  it("renders the collaborators list with expected number of items", async () => {
    const { wrapper } = await render()
    const numCollaborators = collaborators.length
    console.log("lenght", collaborators, numCollaborators)
    const items = wrapper.find("StudioListItem")
    console.log("items", items, items.length)
    expect(items.length).toBe(numCollaborators)
    // First collaborator in list should be editable
    expect(items.at(0).prop("menuOptions")).toHaveLength(2)
    // Last collaborator in list should not be editable
    expect(items.at(numCollaborators - 1).prop("menuOptions")).toHaveLength(0)
    // Should be 6 StudioListItems but only 5 menu buttons (none for the permanent admin)
    expect(items.length).toBe(6)
    expect(wrapper.find(".transparent-button").length).toBe(5)
  })

  it("the edit collaborator icon sets correct state and opens the modal", async () => {
    const { wrapper } = await render()
    wrapper.find(".transparent-button").at(0).simulate("click")

    act(() => {
      wrapper.find("button.dropdown-item").at(0).simulate("click")
    })
    wrapper.update()
    const component = wrapper.find(SiteCollaboratorDrawer)
    expect(component.prop("collaborator")).toStrictEqual(collaborators[0])
    expect(component.prop("visibility")).toBe(true)

    act(() => {
      component.prop("toggleVisibility")()
    })
    wrapper.update()
    expect(wrapper.find(SiteCollaboratorDrawer).prop("visibility")).toBe(false)
  })

  it("the delete collaborator dialog works as expected", async () => {
    const collaborator = collaborators[0]
    deleteCollaboratorStub = helper.mockDeleteRequest(
      siteApiCollaboratorsDetailUrl
        .param({
          name: website.name,
          userId: collaborator.user_id,
        })
        .toString(),
      {},
    )
    const { wrapper } = await render()
    let dialog = wrapper.find("Dialog")
    console.log("length", wrapper.find("li").length)
    wrapper.find(".transparent-button").at(0).simulate("click")
    wrapper.update()
    act(() => {
      wrapper.find("button.dropdown-item").at(1).simulate("click")
    }) 
    wrapper.update()
    dialog = wrapper.find("Dialog")
    expect(dialog.prop("open")).toBe(true)
    expect(dialog.prop("bodyContent")).toContain(collaborators[0].name)
    act(() => {
      dialog.find("ModalFooter").find("button").at(1).simulate("click")
    })
    wrapper.update()
    console.log(wrapper.find(StudioListItem).length)
    sinon.assert.calledOnce(deleteCollaboratorStub)
    dialog = wrapper.find("Dialog")
    expect(dialog.prop("open")).toBe(false)
  })

  it("the add collaborator button sets correct state and opens the modal", async () => {
    const { wrapper } = await render()
    const addLink = wrapper.find("button").at(0)
    act(() => {
      // @ts-expect-error Not simulating whole event
      addLink.prop("onClick")({ preventDefault: helper.sandbox.stub() })
    })
    wrapper.update()
    const component = wrapper.find(SiteCollaboratorDrawer)
    expect(component.prop("collaborator")).toBe(null)
    expect(component.prop("visibility")).toBe(true)

    act(() => {
      component.prop("toggleVisibility")()
    })
    wrapper.update()
    expect(wrapper.find(SiteCollaboratorDrawer).prop("visibility")).toBe(false)
  })
})
