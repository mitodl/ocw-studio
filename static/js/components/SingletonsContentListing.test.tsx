const mockUseRouteMatch = jest.fn()

import React from "react"
import { act } from "react-dom/test-utils"

import SingletonsContentListing from "./SingletonsContentListing"
import WebsiteContext from "../context/Website"

import { siteApiContentDetailUrl } from "../lib/urls"
import * as siteContentFuncs from "../lib/site_content"
import IntegrationTestHelper, {
  TestRenderer
} from "../util/integration_test_helper"
import {
  makeSingletonConfigItem,
  makeSingletonsConfigItem,
  makeWebsiteContentDetail,
  makeWebsiteDetail
} from "../util/factories/websites"

import {
  SingletonConfigItem,
  SingletonsConfigItem,
  Website,
  WebsiteContent
} from "../types/websites"
import sinon, { SinonStub } from "sinon"
import { ContentFormType } from "../types/forms"

jest.mock("react-router-dom", () => ({
  // @ts-ignore
  ...jest.requireActual("react-router-dom"),
  useRouteMatch: mockUseRouteMatch
}))

// ckeditor is not working properly in tests, but we don't need to test it here so just mock it away
function mocko() {
  return <div>mock</div>
}

jest.mock("./widgets/MarkdownEditor", () => ({
  __esModule: true,
  default:    mocko
}))

describe("SingletonsContentListing", () => {
  let helper: IntegrationTestHelper,
    render: TestRenderer,
    website: Website,
    configItem: SingletonsConfigItem,
    singletonConfigItems: SingletonConfigItem[],
    websiteContentDetails: Record<string, WebsiteContent>,
    content: WebsiteContent,
    contentDetailStub: SinonStub

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    content = makeWebsiteContentDetail()
    contentDetailStub = helper.handleRequestStub.returns({
      body:   content,
      status: 200
    })
    website = makeWebsiteDetail()
    singletonConfigItems = [
      makeSingletonConfigItem(),
      makeSingletonConfigItem(),
      makeSingletonConfigItem()
    ]
    configItem = {
      ...makeSingletonsConfigItem(),
      files: singletonConfigItems
    }
    websiteContentDetails = {
      [singletonConfigItems[0].name]: content
    }
    render = helper.configureRenderer(
      props => (
        <WebsiteContext.Provider value={website}>
          <SingletonsContentListing {...props} />
        </WebsiteContext.Provider>
      ),
      {
        website:    website,
        configItem: configItem
      },
      {
        entities: {
          websiteDetails:        { [website.name]: website },
          websiteContentDetails: websiteContentDetails
        },
        queries: {}
      }
    )
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("should render tabs for each singleton config item, showing the first tab on load", async () => {
    const { wrapper } = await render()
    const tabLinks = wrapper.find("NavLink")
    const tabContents = wrapper.find("TabPane")
    expect(tabLinks).toHaveLength(singletonConfigItems.length)
    expect(tabContents).toHaveLength(singletonConfigItems.length)
    const tabText = tabLinks.map(tab => tab.text())
    expect(tabText).toEqual(
      singletonConfigItems.map(singletonConfigItem => singletonConfigItem.label)
    )
    expect(wrapper.find("TabContent").prop("activeTab")).toEqual(0)
    expect(tabLinks.at(0).prop("className")).toEqual("active")
    for (let i = 1; i < tabLinks.length; i++) {
      expect(tabLinks.at(i).prop("className")).toEqual("")
    }
    expect(
      tabContents
        .at(0)
        .find("SiteContentEditor")
        .exists()
    ).toBe(true)
  })

  it("should have working tabs", async () => {
    const tabIndexToSelect = 2
    const { wrapper } = await render()
    const tabLinks = wrapper.find("NavLink")
    act(() => {
      // @ts-ignore
      tabLinks.at(tabIndexToSelect).prop("onClick")({
        preventDefault: helper.sandbox.stub()
      })
    })
    wrapper.update()
    const activeTab = wrapper.find("NavLink").at(tabIndexToSelect)
    expect(activeTab.prop("className")).toEqual("active")
    expect(wrapper.find("TabContent").prop("activeTab")).toEqual(
      tabIndexToSelect
    )
    expect(
      wrapper
        .find("TabPane")
        .at(tabIndexToSelect)
        .find("SiteContentEditor")
        .exists()
    ).toBe(true)
  })

  //
  ;[true, false].forEach(contentContext => {
    it(`loads content detail from the API if needed ${
      contentContext ? "with" : "without"
    } content context`, async () => {
      const needsContentContextStub = helper.sandbox
        .stub(siteContentFuncs, "needsContentContext")
        .returns(contentContext)
      const tabIndexToSelect = 1
      contentDetailStub = helper.handleRequestStub
        .withArgs(
          siteApiContentDetailUrl
            .param({
              name:   website.name,
              textId: singletonConfigItems[tabIndexToSelect].name
            })
            .query(contentContext ? { content_context: true } : {})
            .toString(),
          "GET"
        )
        .returns({
          body:   content,
          status: 200
        })
      const { wrapper } = await render()
      // API should not initially be called since we already have the first item in our websiteContentDetails
      // entities state
      sinon.assert.notCalled(contentDetailStub)
      const tabLink = wrapper.find("NavLink").at(tabIndexToSelect)
      act(() => {
        // @ts-ignore
        tabLink.prop("onClick")({ preventDefault: helper.sandbox.stub() })
      })
      sinon.assert.calledOnce(contentDetailStub)
      sinon.assert.calledWith(
        needsContentContextStub,
        singletonConfigItems[0].fields
      )
    })
  })

  it("should render the SiteContentEditor component", async () => {
    const { wrapper } = await render()
    // Just use the first tab content since its loaded by default
    const tabPane = wrapper.find("TabPane").at(0)
    const siteContentEditor = tabPane.find("SiteContentEditor")
    expect(siteContentEditor.exists()).toBe(true)
    expect(siteContentEditor.props()).toEqual({
      content:     content,
      loadContent: false,
      configItem:  singletonConfigItems[0],
      textId:      singletonConfigItems[0].name,
      formType:    ContentFormType.Edit
    })
  })
})
