import React from "react"
import { act, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import ResourcePickerDialog, { TabIds } from "./ResourcePickerDialog"
import IntegrationTestHelper from "../../testing_utils/IntegrationTestHelper"
import * as hooksState from "../../hooks/state"
import {
  makeWebsiteContentDetail,
  makeWebsiteDetail,
} from "../../util/factories/websites"
import { WebsiteContent } from "../../types/websites"
import {
  RESOURCE_EMBED,
  RESOURCE_LINK,
} from "../../lib/ckeditor/plugins/constants"
import { ResourceType } from "../../constants"
import WebsiteContext from "../../context/Website"
import { Website } from "../../types/websites"
import origResourcePickerListing from "./ResourcePickerListing"

jest.mock("../../hooks/state")
const useDebouncedState = jest.mocked(hooksState.useDebouncedState)

// mock this, otherwise it makes requests and whatnot
jest.mock("./ResourcePickerListing", () => {
  const ResourcePickerListing = jest.fn(() => (
    <div data-testid="resource-picker-listing">mock</div>
  ))
  return {
    __esModule: true,
    default: ResourcePickerListing,
  }
})
const ResourcePickerListing = jest.mocked(origResourcePickerListing)

describe("ResourcePickerDialog", () => {
  let helper: IntegrationTestHelper,
    insertEmbedStub: jest.Mock,
    closeDialogStub: jest.Mock,
    setStub: jest.Mock,
    resource: WebsiteContent,
    website: Website

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    website = makeWebsiteDetail()

    insertEmbedStub = jest.fn()
    closeDialogStub = jest.fn()
    resource = makeWebsiteContentDetail()

    setStub = jest.fn()

    // @ts-expect-error The implementation return is missing some props on DebouncedFn
    useDebouncedState.mockReturnValue(["", setStub])
  })

  afterEach(() => {
    jest.clearAllMocks()
  })

  const renderDialog = (props = {}) => {
    const defaultProps = {
      mode: RESOURCE_EMBED as const,
      contentNames: ["resource", "page"],
      isOpen: true,
      closeDialog: closeDialogStub,
      insertEmbed: insertEmbedStub,
    }

    return helper.render(
      <WebsiteContext.Provider value={website}>
        <ResourcePickerDialog {...defaultProps} {...props} />
      </WebsiteContext.Provider>,
    )
  }

  it.each([
    {
      mode: RESOURCE_EMBED,
      contentNames: ["resource"],
      expectedTabs: ["Videos", "Images"],
    },
    {
      mode: RESOURCE_LINK,
      contentNames: ["resource"],
      expectedTabs: ["Documents", "Videos", "Images", "Other"],
    },
    {
      mode: RESOURCE_LINK,
      contentNames: ["page"],
      expectedTabs: ["Pages"],
    },
    {
      mode: RESOURCE_LINK,
      contentNames: ["resource", "page"],
      expectedTabs: ["Documents", "Videos", "Images", "Other", "Pages"],
    },
  ])(
    "should render tabs based on contentNames. Case: $contentNames",
    async ({ mode, contentNames, expectedTabs }) => {
      const [{ unmount }] = renderDialog({ mode, contentNames })

      for (const tabName of expectedTabs) {
        expect(screen.getByText(tabName)).toBeInTheDocument()
      }

      unmount()
    },
  )

  it.each([
    { modes: [RESOURCE_LINK, RESOURCE_EMBED] as const },
    { modes: [RESOURCE_EMBED, RESOURCE_LINK] as const },
  ])("initially displays resource listing for first tab", async ({ modes }) => {
    const [{ unmount }] = renderDialog({ mode: modes[0] })
    expect(screen.getByTestId("resource-picker-listing")).toBeInTheDocument()
    unmount()
  })

  test("TabIds values are unique", () => {
    const uniqueTabIds = new Set(Object.values(TabIds))
    expect(Object.values(TabIds).length).toBe(uniqueTabIds.size)
  })

  it("should pass some basic props down to the dialog", async () => {
    const [{ unmount }] = renderDialog()
    expect(screen.getByRole("dialog")).toBeInTheDocument()
    unmount()
  })

  it.each([
    {
      mode: RESOURCE_LINK,
      attaching: "linking",
      acceptText: "Add link",
    },
    {
      mode: RESOURCE_EMBED,
      attaching: "embedding",
      acceptText: "Embed resource",
    },
  ])(
    "should allow focusing and $attaching a resource, then close the dialog",
    async ({ mode, acceptText }) => {
      const user = userEvent.setup()
      const [{ unmount }] = renderDialog({ mode })

      // Simulate focusing a resource by calling the mock's focusResource prop
      await act(async () => {
        const focusResourceCall =
          ResourcePickerListing.mock.calls[0][0].focusResource
        focusResourceCall(resource)
      })

      await waitFor(() => {
        expect(
          screen.getByRole("button", { name: acceptText }),
        ).toBeInTheDocument()
      })

      await user.click(screen.getByRole("button", { name: acceptText }))

      expect(insertEmbedStub).toHaveBeenCalledWith(
        resource.text_id,
        resource.title,
        mode,
      )
      expect(closeDialogStub).toHaveBeenCalledTimes(1)

      unmount()
    },
  )

  it.each([
    {
      index: 0,
      resourcetype: ResourceType.Document,
      contentType: "resource",
      singleColumn: true,
      tabName: "Documents",
    },
    {
      index: 1,
      resourcetype: ResourceType.Video,
      contentType: "resource",
      singleColumn: false,
      tabName: "Videos",
    },
    {
      index: 2,
      resourcetype: ResourceType.Image,
      contentType: "resource",
      singleColumn: false,
      tabName: "Images",
    },
    {
      index: 3,
      resourcetype: ResourceType.Other,
      contentType: "resource",
      singleColumn: true,
      tabName: "Other",
    },
    {
      index: 4,
      resourcetype: null,
      contentType: "page",
      singleColumn: true,
      tabName: "Pages",
    },
  ])(
    "passes the correct props to ResourcePickerListing when main tab $index is clicked",
    async ({ resourcetype, contentType, singleColumn, tabName }) => {
      const user = userEvent.setup()
      const [{ unmount }] = renderDialog({ mode: RESOURCE_LINK })

      const tab = screen.getByText(tabName)
      await user.click(tab)

      await waitFor(() => {
        const lastCall =
          ResourcePickerListing.mock.calls[
            ResourcePickerListing.mock.calls.length - 1
          ][0]
        expect(lastCall.resourcetype).toEqual(resourcetype)
        expect(lastCall.contentType).toBe(contentType)
        expect(lastCall.singleColumn).toBe(singleColumn)
      })

      unmount()
    },
  )

  it("should pass filter string to picker, when filter is set", async () => {
    const user = userEvent.setup()
    const setStub = jest.fn()
    // @ts-expect-error The implementation return is missing some props on DebouncedFn
    useDebouncedState.mockImplementation((initial, _ms) => {
      return [initial, setStub]
    })

    const [{ unmount }] = renderDialog()

    const filterInput = screen.getByRole("textbox")
    await user.type(filterInput, "new filter")

    expect(setStub).toHaveBeenCalled()

    unmount()
  })
})
