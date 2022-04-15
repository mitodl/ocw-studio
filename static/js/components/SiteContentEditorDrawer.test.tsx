import React from "react"
import { act } from "react-dom/test-utils"
import * as rrDOM from "react-router-dom"

import WebsiteContext from "../context/Website"

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
import ConfirmDiscardChanges from "./util/ConfirmDiscardChanges"
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
    fetchWebsiteContentListing: any

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    website = makeWebsiteDetail()
    configItem = makeRepeatableConfigItem("resource")
    contentItem = makeWebsiteContentDetail()

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

  it("sets `when` on ConfirmDiscardChanges based on dirtyness", async () => {
    const { wrapper } = await render()
    const siteContentEditor = wrapper.find(SiteContentEditor)

    expect(wrapper.find(ConfirmDiscardChanges).prop("when")).toBe(false)
    act(() => siteContentEditor.prop("setDirty")(true))
    expect(
      wrapper
        .update()
        .find(ConfirmDiscardChanges)
        .prop("when")
    ).toBe(true)
    act(() => siteContentEditor.prop("setDirty")(false))
    expect(
      wrapper
        .update()
        .find(ConfirmDiscardChanges)
        .prop("when")
    ).toBe(false)
  })

  describe("closing the drawer", () => {
    const setup = async ({
      dirty,
      closeFrom
    }: {
      dirty: boolean
      closeFrom: "modal" | "editor"
    }) => {
      const { wrapper } = await render({ website })
      const siteContentEditor = wrapper.find(SiteContentEditor)
      const initialLocation = helper.browserHistory.location
      act(() => siteContentEditor.prop("setDirty")(dirty))
      if (closeFrom === "modal") {
        act(() => {
          wrapper.find(BasicModal).prop("hideModal")()
        })
      } else {
        act(() => {
          wrapper.find(SiteContentEditor).prop("dismiss")!()
        })
      }

      return { initialLocation, wrapper }
    }

    it.each([
      { closeFrom: "modal" as const },
      { closeFrom: "editor" as const }
    ])(
      "does not close the modal if dirty and confirmation is denied [closed from $closeFrom]",
      async ({ closeFrom }) => {
        window.mockConfirm.mockReturnValueOnce(false)
        const { wrapper, initialLocation } = await setup({
          dirty: true,
          closeFrom
        })

        expect(
          wrapper
            .update()
            .find(BasicModal)
            .prop("isVisible")
        ).toBe(true)
        expect(helper.browserHistory.location).toBe(initialLocation)
      }
    )

    it.each([
      { closeFrom: "modal" as const },
      { closeFrom: "editor" as const }
    ])(
      "closes the modal without confirmation if not dirty",
      async ({ closeFrom }) => {
        const { wrapper, initialLocation } = await setup({
          dirty: false,
          closeFrom
        })

        expect(initialLocation.pathname).toBe("/")
        expect(
          wrapper
            .update()
            .find(BasicModal)
            .prop("isVisible")
        ).toBe(false)
        expect(helper.browserHistory.location.pathname).toBe(
          `/sites/${website.name}/type/resource/`
        )
        expect(window.mockConfirm).not.toHaveBeenCalled()
      }
    )

    it.each([
      { closeFrom: "modal" as const },
      { closeFrom: "editor" as const }
    ])("closes the modal with confirmation if dirty", async ({ closeFrom }) => {
      window.mockConfirm.mockReturnValueOnce(true)
      const { wrapper, initialLocation } = await setup({
        dirty: true,
        closeFrom
      })

      expect(initialLocation.pathname).toBe("/")
      expect(
        wrapper
          .update()
          .find(BasicModal)
          .prop("isVisible")
      ).toBe(false)
      expect(helper.browserHistory.location.pathname).toBe(
        `/sites/${website.name}/type/resource/`
      )
    })
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
