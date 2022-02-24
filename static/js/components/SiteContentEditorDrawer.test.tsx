import React from "react"
import { act } from "react-dom/test-utils"
import * as rrDOM from "react-router-dom"

import WebsiteContext from "../context/Website"

import useConfirmation from "../hooks/confirmation"
import { siteApiContentDetailUrl } from "../lib/urls"
import IntegrationTestHelper, {
  TestRenderer
} from "../util/integration_test_helper"
import {
  makeRepeatableConfigItem,
  makeWebsiteContentDetail,
  makeWebsiteDetail
} from "../util/factories/websites"

import {
  RepeatableConfigItem,
  Website,
  WebsiteContent
} from "../types/websites"
import SiteContentEditor from "./SiteContentEditor"
import SiteContentEditorDrawer from "./SiteContentEditorDrawer"
import { Editing } from "../types/modal_state"
import ConfirmationModal from "./ConfirmationModal"
import BasicModal from "./BasicModal"

const { useParams } = rrDOM as jest.Mocked<typeof rrDOM>

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
  __esModule: true,
  ...jest.requireActual("react-router-dom"),
  useParams:  jest.fn()
}))

describe("SiteContentEditorDrawer", () => {
  let helper: IntegrationTestHelper,
    render: TestRenderer,
    website: Website,
    configItem: RepeatableConfigItem,
    contentItem: WebsiteContent,
    setConfirmationModalVisible: any,
    conditionalClose: any,
    fetchWebsiteContentListing: any

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    website = makeWebsiteDetail()
    configItem = makeRepeatableConfigItem("resource")
    contentItem = makeWebsiteContentDetail()

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
    useParams.mockClear()
    useParams.mockReturnValue({})

    fetchWebsiteContentListing = jest.fn()

    helper.mockGetRequest(
      siteApiContentDetailUrl
        .param({
          name:   website.name,
          textId: contentItem.text_id
        })
        .toString(),
      contentItem
    )

    render = helper.configureRenderer(
      props => (
        <WebsiteContext.Provider value={website}>
          <SiteContentEditorDrawer {...props} />
        </WebsiteContext.Provider>
      ),
      { configItem, fetchWebsiteContentListing }
    )
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("passes setDirty to SiteContentEditor", async () => {
    const { wrapper } = await render()
    const siteContentEditor = wrapper.find(SiteContentEditor)
    const setDirty =
      // @ts-ignore
      useConfirmation.mock.calls[useConfirmation.mock.calls.length - 1][0]
        .setDirty
    expect(siteContentEditor.prop("setDirty")).toBe(setDirty)
  })

  it("sets visibility on the confirmation modal", async () => {
    const { wrapper } = await render({ website })
    const setVisible = wrapper
      .find(ConfirmationModal)
      .prop("setConfirmationModalVisible")
    act(() => setVisible(true))
    expect(setConfirmationModalVisible).toBeCalledWith(true)
  })

  it("dismisses a modal", async () => {
    const { wrapper } = await render({ website })
    act(() => {
      wrapper.find(ConfirmationModal).prop("dismiss")()
    })
    expect(conditionalClose).toBeCalledWith(true)
  })

  it("hides the drawer, maybe with a confirmation dialog first", async () => {
    const { wrapper } = await render({ website })
    act(() => {
      wrapper
        .find(BasicModal)
        .at(1)
        .prop("hideModal")()
    })
    expect(conditionalClose).toBeCalledWith(false)
  })

  it("dismisses a modal from the editor", async () => {
    const { wrapper } = await render()
    const editorModal = wrapper.find("BasicModal").at(1)
    const siteContentEditor = editorModal.find(SiteContentEditor)
    act(() => {
      siteContentEditor.prop("dismiss")!()
    })

    expect(conditionalClose).toBeCalledWith(true)
  })

  it("sets a dirty flag", async () => {
    const { wrapper } = await render({ website })
    expect(wrapper.find("ConfirmationModal").prop("dirty")).toBeFalsy()
    const setDirty =
      // @ts-ignore
      useConfirmation.mock.calls[useConfirmation.mock.calls.length - 1][0]
        .setDirty
    act(() => setDirty(true))
    wrapper.update()
    expect(wrapper.find("ConfirmationModal").prop("dirty")).toBeTruthy()
  })

  it("gets uuid prop for editing", async () => {
    useParams.mockReturnValue({ uuid: contentItem.text_id })
    const { wrapper } = await render()
    const editor = wrapper.find(SiteContentEditor)
    expect(editor.prop("editorState").editing()).toBeTruthy()
    expect((editor.prop("editorState") as Editing<string>).wrapped).toBe(
      contentItem.text_id
    )
  })

  it("should pass fetchWebsiteContentListing to the Editor", async () => {
    const { wrapper } = await render()
    expect(
      wrapper.find(SiteContentEditor).prop("fetchWebsiteContentListing")
    ).toBe(fetchWebsiteContentListing)
  })
})
