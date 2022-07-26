import React from "react"
import { act } from "react-dom/test-utils"
import sinon, { SinonStub } from "sinon"
import SingletonsContentListing from "./SingletonsContentListing"
import WebsiteContext from "../context/Website"

import { siteApiContentDetailUrl } from "../lib/urls"
import * as siteContentFuncs from "../lib/site_content"
import IntegrationTestHelper, {
  TestRenderer
} from "../util/integration_test_helper_old"
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
import SiteContentEditor from "./SiteContentEditor"
import ConfirmDiscardChanges from "./util/ConfirmDiscardChanges"
import { flushEventQueue } from "../test_util"

// Check test failure on github actions

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

  it.each([
    { contentContext: true, preposition: "with" },
    { contentContext: false, preposition: "without" }
  ])(
    "loads content detail from the API if needed $preposition content context",
    async ({ contentContext }) => {
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
    }
  )

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

  it.each([
    { dirty: true, confirmCalls: 1 },
    { dirty: false, confirmCalls: 0 }
  ])(
    "prompts for confirmation on pathname change iff discarding dirty state [dirty=$dirty]",
    async ({ dirty, confirmCalls }) => {
      const { wrapper } = await render()
      const editor = wrapper.find(SiteContentEditor).first()

      act(() => editor.prop("setDirty")(dirty))

      expect(window.mockConfirm).toHaveBeenCalledTimes(0)
      helper.browserHistory.push("/elsewhere")
      expect(window.mockConfirm).toHaveBeenCalledTimes(confirmCalls)
      if (confirmCalls > 0) {
        expect(window.mockConfirm.mock.calls[0][0]).toMatch(
          /Are you sure you want to discard your changes\?/
        )
      }
    }
  )

  it.each([
    { dirty: true, confirmCalls: 1 },
    { dirty: false, confirmCalls: 0 }
  ])(
    "prompts for confirmation on publish iff state is dirty [dirty=$dirty]",
    async ({ dirty, confirmCalls }) => {
      const { wrapper } = await render()
      const editor = wrapper.find(SiteContentEditor).first()

      act(() => editor.prop("setDirty")(dirty))

      expect(window.mockConfirm).toHaveBeenCalledTimes(0)
      helper.browserHistory.push("?publish=")
      expect(window.mockConfirm).toHaveBeenCalledTimes(confirmCalls)
      if (confirmCalls > 0) {
        expect(window.mockConfirm.mock.calls[0][0]).toMatch(
          /Are you sure you want to publish\?/
        )
      }
    }
  )

  it.each([true, false])(
    "changes route and unmounts when dirty iff confirmed",
    async confirmed => {
      const { wrapper } = await render()
      const editor = wrapper.find(SiteContentEditor).first()

      act(() => editor.prop("setDirty")(true))
      window.mockConfirm.mockReturnValue(confirmed)

      expect(helper.browserHistory.location.pathname).toBe("/")
      helper.browserHistory.push("/elsewhere")
      if (confirmed) {
        expect(helper.browserHistory.location.pathname).toBe("/elsewhere")
      } else {
        expect(helper.browserHistory.location.pathname).toBe("/")
      }
    }
  )

  it("clears a dirty flag when the path changes", async () => {
    const { wrapper } = await render()
    const editor = wrapper.find(SiteContentEditor).first()

    act(() => editor.prop("setDirty")(true))

    expect(
      wrapper
        .update()
        .find(ConfirmDiscardChanges)
        .prop("when")
    ).toBe(true)

    window.mockConfirm.mockReturnValue(true)
    helper.browserHistory.push("/pages")
    await flushEventQueue()
    expect(
      wrapper
        .update()
        .find(ConfirmDiscardChanges)
        .prop("when")
    ).toBe(false)
  })
})
