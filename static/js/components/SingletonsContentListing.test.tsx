// Mock the Prompt component to track when it's called
jest.mock("./util/Prompt", () => {
  return {
    __esModule: true,
    default: jest.fn(() => null),
  }
})

import React from "react"
import { act } from "react-dom/test-utils"
import sinon, { SinonStub } from "sinon"
import SingletonsContentListing from "./SingletonsContentListing"
import WebsiteContext from "../context/Website"

import { siteApiContentDetailUrl } from "../lib/urls"
import * as siteContentFuncs from "../lib/site_content"
import IntegrationTestHelper, {
  TestRenderer,
} from "../util/integration_test_helper_old"
import {
  makeSingletonConfigItem,
  makeSingletonsConfigItem,
  makeWebsiteContentDetail,
  makeWebsiteDetail,
} from "../util/factories/websites"

import {
  SingletonConfigItem,
  SingletonsConfigItem,
  Website,
  WebsiteContent,
} from "../types/websites"
import { createModalState } from "../types/modal_state"
import SiteContentEditor from "./SiteContentEditor"
import ConfirmDiscardChanges from "./util/ConfirmDiscardChanges"
import { flushEventQueue } from "../test_util"
import Prompt from "./util/Prompt"

const mockPrompt = Prompt as jest.MockedFunction<typeof Prompt>

// ckeditor is not working properly in tests, but we don't need to test it here so just mock it away
function mocko() {
  return <div>mock</div>
}

jest.mock("../lib/site_content", () => {
  return {
    __esModule: true,
    ...jest.requireActual("../lib/site_content"),
  }
})

jest.mock("./widgets/MarkdownEditor", () => ({
  __esModule: true,
  default: mocko,
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
      body: content,
      status: 200,
    })
    website = makeWebsiteDetail()
    singletonConfigItems = [
      makeSingletonConfigItem(),
      makeSingletonConfigItem(),
      makeSingletonConfigItem(),
    ]
    configItem = {
      ...makeSingletonsConfigItem(),
      files: singletonConfigItems,
    }
    websiteContentDetails = {
      [singletonConfigItems[0].name]: content,
    }
    render = helper.configureRenderer(
      (props) => (
        <WebsiteContext.Provider value={website}>
          <SingletonsContentListing {...props} />
        </WebsiteContext.Provider>
      ),
      {
        website: website,
        configItem: configItem,
      },
      {
        entities: {
          websiteDetails: { [website.name]: website },
          websiteContentDetails: websiteContentDetails,
        },
        queries: {},
      },
    )

    // Clear mocks
    mockPrompt.mockClear()
    window.mockConfirm.mockClear()
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
    const tabText = tabLinks.map((tab) => tab.text())
    expect(tabText).toEqual(
      singletonConfigItems.map(
        (singletonConfigItem) => singletonConfigItem.label,
      ),
    )
    expect(wrapper.find("TabContent").prop("activeTab")).toEqual(0)
    expect(tabLinks.at(0).prop("className")).toEqual("active")
    for (let i = 1; i < tabLinks.length; i++) {
      expect(tabLinks.at(i).prop("className")).toEqual("")
    }
    expect(tabContents.at(0).find("SiteContentEditor").exists()).toBe(true)
  })

  it("should have working tabs", async () => {
    const tabIndexToSelect = 2
    const { wrapper } = await render()
    const tabLinks = wrapper.find("NavLink")
    act(() => {
      // @ts-expect-error Not mocking whole event
      tabLinks.at(tabIndexToSelect).prop("onClick")({
        preventDefault: helper.sandbox.stub(),
      })
    })
    wrapper.update()
    const activeTab = wrapper.find("NavLink").at(tabIndexToSelect)
    expect(activeTab.prop("className")).toEqual("active")
    expect(wrapper.find("TabContent").prop("activeTab")).toEqual(
      tabIndexToSelect,
    )
    expect(
      wrapper
        .find("TabPane")
        .at(tabIndexToSelect)
        .find("SiteContentEditor")
        .exists(),
    ).toBe(true)
  })

  it.each([
    { contentContext: true, preposition: "with" },
    { contentContext: false, preposition: "without" },
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
              name: website.name,
              textId: singletonConfigItems[tabIndexToSelect].name,
            })
            .query(contentContext ? { content_context: true } : {})
            .toString(),
          "GET",
        )
        .returns({
          body: newContent,
          status: 200,
        })
      const { wrapper } = await render()
      // API should not initially be called since we already have the first item in our websiteContentDetails
      // entities state
      sinon.assert.notCalled(contentDetailStub)
      const tabLink = wrapper.find("NavLink").at(tabIndexToSelect)
      act(() => {
        // @ts-expect-error Not mocking whole event
        tabLink.prop("onClick")({ preventDefault: helper.sandbox.stub() })
      })
      wrapper.update()
      sinon.assert.calledOnce(contentDetailStub)
      sinon.assert.calledWith(
        needsContentContextStub,
        singletonConfigItems[tabIndexToSelect].fields,
      )
      expect(
        wrapper.find("SiteContentEditor").at(tabIndexToSelect).prop("content"),
      ).toBe(newContent)
      wrapper.find("SiteContentEditor").forEach((editorWrapper, idx) => {
        if (idx !== tabIndexToSelect) {
          expect(editorWrapper.prop("content")).toBeNull()
        }
      })
    },
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
      createModalState("editing", singletonConfigItems[0].name),
    )
  })

  it.each([
    { dirty: true, expectedWhen: true },
    { dirty: false, expectedWhen: false },
  ])(
    "ConfirmDiscardChanges shows correct when prop based on dirty state [dirty=$dirty]",
    async ({ dirty, expectedWhen }) => {
      const { wrapper } = await render()
      const editor = wrapper.find(SiteContentEditor).first()

      act(() => editor.prop("setDirty")(dirty))
      wrapper.update()

      expect(wrapper.find(ConfirmDiscardChanges).prop("when")).toBe(
        expectedWhen,
      )
    },
  )

  it("ConfirmDiscardChanges is rendered with when=true when dirty", async () => {
    const { wrapper } = await render()
    const editor = wrapper.find(SiteContentEditor).first()

    act(() => editor.prop("setDirty")(true))
    wrapper.update()

    const confirmComponent = wrapper.find(ConfirmDiscardChanges)
    expect(confirmComponent.prop("when")).toBe(true)
  })

  it("navigation works correctly - location can be changed", async () => {
    await render()

    expect(helper.browserHistory.location.pathname).toBe("/")
    act(() => {
      helper.browserHistory.push("/elsewhere")
    })
    expect(helper.browserHistory.location.pathname).toBe("/elsewhere")
  })

  it("clears dirty flag when pathname changes", async () => {
    const { wrapper } = await render()
    const editor = wrapper.find(SiteContentEditor).first()

    // Set dirty state
    act(() => editor.prop("setDirty")(true))
    wrapper.update()

    expect(wrapper.find(ConfirmDiscardChanges).prop("when")).toBe(true)

    // Navigate to a different path - this should trigger the useEffect that clears dirty state
    act(() => {
      helper.browserHistory.push("/pages")
    })
    await flushEventQueue()
    wrapper.update()

    // The dirty flag should be cleared due to pathname change
    expect(wrapper.find(ConfirmDiscardChanges).prop("when")).toBe(false)
  })
})
