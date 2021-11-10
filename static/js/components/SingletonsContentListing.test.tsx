import React from "react"
import { act } from "react-dom/test-utils"
import { useLocation } from "react-router-dom"
import sinon, { SinonStub } from "sinon"

import SingletonsContentListing from "./SingletonsContentListing"
import WebsiteContext from "../context/Website"
import useConfirmation from "../hooks/confirmation"

import { siteApiContentDetailUrl } from "../lib/urls"
import * as siteContentFuncs from "../lib/site_content"
import configureStore from "../store/configureStore"
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
import { createModalState } from "../types/modal_state"

// ckeditor is not working properly in tests, but we don't need to test it here so just mock it away
function mocko() {
  return <div>mock</div>
}

jest.mock("./widgets/MarkdownEditor", () => ({
  __esModule: true,
  default:    mocko
}))
jest.mock("../hooks/confirmation", () => ({
  __esModule: true,
  default:    jest.fn()
}))
jest.mock("react-router-dom", () => ({
  __esModule:  true,
  ...jest.requireActual("react-router-dom"),
  useLocation: jest.fn()
}))

describe("SingletonsContentListing", () => {
  let helper: IntegrationTestHelper,
    render: TestRenderer,
    website: Website,
    configItem: SingletonsConfigItem,
    singletonConfigItems: SingletonConfigItem[],
    websiteContentDetails: Record<string, WebsiteContent>,
    content: WebsiteContent,
    contentDetailStub: SinonStub,
    setConfirmationModalVisible: any,
    conditionalClose: any

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
    setConfirmationModalVisible = jest.fn()
    conditionalClose = jest.fn()
    // @ts-ignore
    useConfirmation.mockClear()
    // @ts-ignore
    useConfirmation.mockReturnValue({
      confirmationModalVisible: false,
      setConfirmationModalVisible,
      conditionalClose
    })
    // @ts-ignore
    useLocation.mockClear()
    // @ts-ignore
    useLocation.mockReturnValue({
      pathname: "/path/to/a/page"
    })
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
      const newContent = makeWebsiteContentDetail()
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
          body:   newContent,
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
      wrapper.update()
      sinon.assert.calledOnce(contentDetailStub)
      sinon.assert.calledWith(
        needsContentContextStub,
        singletonConfigItems[tabIndexToSelect].fields
      )
      expect(
        wrapper
          .find("SiteContentEditor")
          .at(tabIndexToSelect)
          .prop("content")
      ).toBe(newContent)
      wrapper.find("SiteContentEditor").forEach((editorWrapper, idx) => {
        if (idx !== tabIndexToSelect) {
          expect(editorWrapper.prop("content")).toBeNull()
        }
      })
    })
  })

  it("should render the SiteContentEditor component", async () => {
    const { wrapper } = await render()
    // Just use the first tab content since its loaded by default
    const tabPane = wrapper.find("TabPane").at(0)
    const siteContentEditor = tabPane.find("SiteContentEditor")
    expect(siteContentEditor.exists()).toBe(true)
    expect(siteContentEditor.prop("content")).toBe(content)
    expect(siteContentEditor.prop("loadContent")).toBeFalsy()
    expect(siteContentEditor.prop("configItem")).toBe(singletonConfigItems[0])
    expect(siteContentEditor.prop("editorState")).toStrictEqual(
      createModalState("editing", singletonConfigItems[0].name)
    )
  })

  it("uses visibility from useConfirmation", async () => {
    // @ts-ignore
    useConfirmation.mockReturnValue({
      confirmationModalVisible: true,
      setConfirmationModalVisible,
      conditionalClose
    })
    const { wrapper } = await render({ website })
    expect(
      wrapper.find("ConfirmationModal").prop("confirmationModalVisible")
    ).toBeTruthy()
  })

  it("sets visibility on the confirmation modal", async () => {
    const { wrapper } = await render({ website })
    const setVisible = wrapper
      .find("ConfirmationModal")
      .prop("setConfirmationModalVisible")
    // @ts-ignore
    act(() => setVisible(true))
    expect(setConfirmationModalVisible).toBeCalledWith(true)
  })

  it("dismisses a modal", async () => {
    const { wrapper } = await render({ website })
    // @ts-ignore
    wrapper.find("ConfirmationModal").prop("dismiss")()
    expect(conditionalClose).toBeCalledWith(true)
  })

  it("sets a dirty flag", async () => {
    const { wrapper } = await render()
    expect(wrapper.find("ConfirmationModal").prop("dirty")).toBeFalsy()
    const setDirty =
      // @ts-ignore
      useConfirmation.mock.calls[useConfirmation.mock.calls.length - 1][0]
        .setDirty
    // @ts-ignore
    for (const editor of wrapper.find("SiteContentEditor").map(item => item)) {
      expect(editor.prop("setDirty")).toBe(setDirty)
    }
    act(() => setDirty(true))
    wrapper.update()
    expect(wrapper.find("ConfirmationModal").prop("dirty")).toBeTruthy()
  })

  it("clears a dirty flag when the path changes", async () => {
    const { wrapper } = await render()
    expect(wrapper.find("ConfirmationModal").prop("dirty")).toBeFalsy()
    const setDirty =
      // @ts-ignore
      useConfirmation.mock.calls[useConfirmation.mock.calls.length - 1][0]
        .setDirty
    act(() => setDirty(true))
    // @ts-ignore
    useLocation.mockReturnValue({
      pathname: "/resources"
    })

    // force a rerender so it picks up the changed location
    await wrapper.setProps({
      store: configureStore({ entities: {}, queries: {} })
    })

    // @ts-ignore
    wrapper.update()
    expect(wrapper.find("ConfirmationModal").prop("dirty")).toBeFalsy()
  })
})
