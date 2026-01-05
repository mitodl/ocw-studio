import React from "react"
import { act, screen, waitFor } from "@testing-library/react"
import * as rrDOM from "react-router-dom"

import { siteApiContentDetailUrl } from "../lib/urls"
import { IntegrationTestHelper } from "../testing_utils"
import {
  makeRepeatableConfigItem,
  makeWebsiteContentDetail,
  makeWebsiteDetail,
} from "../util/factories/websites"

import {
  RepeatableConfigItem,
  Website,
  WebsiteContent,
} from "../types/websites"
import SiteContentEditorDrawer from "./SiteContentEditorDrawer"
import { Editing } from "../types/modal_state"
import { SiteContentEditorProps } from "./SiteContentEditor"
import { WebsiteContentModalState } from "../types/websites"

const { useParams } = rrDOM as jest.Mocked<typeof rrDOM>

function mocko() {
  return <div>mock</div>
}

jest.mock("./widgets/MarkdownEditor", () => ({
  __esModule: true,
  default: mocko,
}))
jest.mock("react-router-dom", () => ({
  __esModule: true,
  ...jest.requireActual("react-router-dom"),
  useParams: jest.fn(),
}))

jest.mock("./BasicModal", () => ({
  __esModule: true,
  default: ({
    isVisible,
    hideModal,
    children,
  }: {
    isVisible: boolean
    hideModal: () => void
    title: string
    className?: string
    children: (props: { hideModal: () => void }) => JSX.Element | null
  }) => {
    if (!isVisible) return null
    return (
      <div data-testid="basic-modal">
        <button aria-label="close" onClick={hideModal}>
          Close
        </button>
        {children({ hideModal })}
      </div>
    )
  },
}))

interface CapturedEditorProps {
  setDirty: (dirty: boolean) => void
  dismiss?: () => void
  editorState: WebsiteContentModalState
  fetchWebsiteContentListing?: any
}

let capturedEditorProps: CapturedEditorProps | null = null

jest.mock("./SiteContentEditor", () => ({
  __esModule: true,
  default: (props: SiteContentEditorProps) => {
    capturedEditorProps = {
      setDirty: props.setDirty,
      dismiss: props.dismiss,
      editorState: props.editorState,
      fetchWebsiteContentListing: props.fetchWebsiteContentListing,
    }
    return <div data-testid="site-content-editor">Mock Editor</div>
  },
}))

describe("SiteContentEditorDrawer", () => {
  let helper: IntegrationTestHelper,
    website: Website,
    configItem: RepeatableConfigItem,
    contentItem: WebsiteContent,
    fetchWebsiteContentListing: jest.Mock

  beforeEach(() => {
    capturedEditorProps = null
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
          name: website.name,
          textId: contentItem.text_id,
        })
        .toString(),
      contentItem,
    )
  })

  afterEach(() => {
    jest.restoreAllMocks()
  })

  const renderComponent = async () => {
    const [result, { history }] = helper.renderWithWebsite(
      <SiteContentEditorDrawer
        configItem={configItem}
        fetchWebsiteContentListing={fetchWebsiteContentListing}
      />,
      website,
    )

    await waitFor(() => {
      expect(capturedEditorProps).not.toBeNull()
    })

    return { result, history }
  }

  it("sets `when` on ConfirmDiscardChanges based on dirtyness", async () => {
    const { history } = await renderComponent()
    const initialLocation = history.location

    window.mockConfirm.mockReturnValue(false)
    act(() => capturedEditorProps!.setDirty(false))
    act(() => {
      history.push("/other-page")
    })
    expect(history.location.pathname).toBe("/other-page")
    expect(window.mockConfirm).not.toHaveBeenCalled()

    act(() => {
      history.push(initialLocation.pathname)
    })

    act(() => capturedEditorProps!.setDirty(true))
    act(() => {
      history.push("/another-page")
    })
    expect(window.mockConfirm).toHaveBeenCalled()
    expect(history.location.pathname).toBe(initialLocation.pathname)

    window.mockConfirm.mockClear()
    act(() => capturedEditorProps!.setDirty(false))
    act(() => {
      history.push("/yet-another-page")
    })
    expect(window.mockConfirm).not.toHaveBeenCalled()
    expect(history.location.pathname).toBe("/yet-another-page")
  })

  describe("closing the drawer", () => {
    const setup = async ({
      dirty,
      closeFrom,
    }: {
      dirty: boolean
      closeFrom: "modal" | "editor"
    }) => {
      const { history } = await renderComponent()
      const initialLocation = history.location

      act(() => capturedEditorProps!.setDirty(dirty))

      if (closeFrom === "modal") {
        const closeButton = screen.getByRole("button", { name: /close/i })
        act(() => {
          closeButton.click()
        })
      } else {
        act(() => {
          capturedEditorProps!.dismiss!()
        })
      }

      return { initialLocation, history }
    }

    it.each([
      { closeFrom: "modal" as const },
      { closeFrom: "editor" as const },
    ])(
      "does not close the modal if dirty and confirmation is denied [closed from $closeFrom]",
      async ({ closeFrom }) => {
        window.mockConfirm.mockReturnValueOnce(false)
        const { history, initialLocation } = await setup({
          dirty: true,
          closeFrom,
        })

        expect(screen.getByTestId("site-content-editor")).toBeInTheDocument()
        expect(history.location).toBe(initialLocation)
      },
    )

    it.each([
      { closeFrom: "modal" as const },
      { closeFrom: "editor" as const },
    ])(
      "closes the modal without confirmation if not dirty",
      async ({ closeFrom }) => {
        const { history, initialLocation } = await setup({
          dirty: false,
          closeFrom,
        })

        expect(initialLocation.pathname).toBe("/")
        expect(history.location.pathname).toBe(
          `/sites/${website.name}/type/resource/`,
        )
        expect(window.mockConfirm).not.toHaveBeenCalled()
      },
    )

    it.each([
      { closeFrom: "modal" as const },
      { closeFrom: "editor" as const },
    ])("closes the modal with confirmation if dirty", async ({ closeFrom }) => {
      window.mockConfirm.mockReturnValueOnce(true)
      const { history, initialLocation } = await setup({
        dirty: true,
        closeFrom,
      })

      expect(initialLocation.pathname).toBe("/")
      expect(history.location.pathname).toBe(
        `/sites/${website.name}/type/resource/`,
      )
    })
  })

  it("gets uuid prop for editing", async () => {
    useParams.mockReturnValue({ uuid: contentItem.text_id })
    await renderComponent()

    expect(capturedEditorProps!.editorState.editing()).toBeTruthy()
    expect((capturedEditorProps!.editorState as Editing<string>).wrapped).toBe(
      contentItem.text_id,
    )
  })

  it("should pass fetchWebsiteContentListing to the Editor", async () => {
    await renderComponent()
    expect(capturedEditorProps!.fetchWebsiteContentListing).toBe(
      fetchWebsiteContentListing,
    )
  })
})
