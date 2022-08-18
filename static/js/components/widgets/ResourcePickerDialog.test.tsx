import React from "react"
import { act } from "react-dom/test-utils"
import { TabPane, NavLink } from "reactstrap"
import { ReactWrapper } from "enzyme"

import ResourcePickerDialog, { TabIds } from "./ResourcePickerDialog"
import IntegrationTestHelper, {
  TestRenderer
} from "../../util/integration_test_helper_old"
import { useDebouncedState } from "../../hooks/state"
import { useState } from "react"
import {
  makeWebsiteContentDetail,
  makeWebsiteDetail
} from "../../util/factories/websites"
import { WebsiteContent } from "../../types/websites"
import {
  RESOURCE_EMBED,
  RESOURCE_LINK
} from "../../lib/ckeditor/plugins/constants"
import { ResourceType } from "../../constants"
import Dialog from "../Dialog"
import WebsiteContext from "../../context/Website"
import { Website } from "../../types/websites"

jest.mock("../../hooks/state")

function ResourcePickerListing() {
  return <div>mock</div>
}

// mock this, otherwise it makes requests and whatnot
jest.mock("./ResourcePickerListing", () => ({
  __esModule: true,
  default:    ResourcePickerListing
}))

const focusResource = (wrapper: ReactWrapper, resource: WebsiteContent) => {
  act(() => {
    // @ts-ignore
    wrapper.find("ResourcePickerListing").prop("focusResource")(resource)
  })
  wrapper.update()
}

describe("ResourcePickerDialog", () => {
  let helper: IntegrationTestHelper,
    render: TestRenderer,
    insertEmbedStub: sinon.SinonStub,
    closeDialogStub: sinon.SinonStub,
    setStub: sinon.SinonStub,
    resource: WebsiteContent,
    website: Website

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    website = makeWebsiteDetail()

    insertEmbedStub = helper.sandbox.stub()
    closeDialogStub = helper.sandbox.stub()
    resource = makeWebsiteContentDetail()

    setStub = helper.sandbox.stub()
    // @ts-ignore
    useDebouncedState.mockReturnValue(["", setStub])

    render = helper.configureRenderer(
      props => (
        <WebsiteContext.Provider value={website}>
          <ResourcePickerDialog {...props} />
        </WebsiteContext.Provider>
      ),
      {
        mode:         RESOURCE_EMBED,
        contentNames: ["resource", "page"],
        isOpen:       true,
        closeDialog:  closeDialogStub,
        insertEmbed:  insertEmbedStub
      }
    )
  })

  afterEach(() => {
    helper.cleanup()
  })

  it.each([
    {
      mode:         RESOURCE_EMBED,
      contentNames: ["resource"],
      expectedTabs: [TabIds.Videos, TabIds.Images]
    },
    {
      mode:         RESOURCE_LINK,
      contentNames: ["resource"],
      expectedTabs: [
        TabIds.Documents,
        TabIds.Videos,
        TabIds.Images,
        TabIds.Other
      ]
    },
    {
      mode:         RESOURCE_LINK,
      contentNames: ["page"],
      expectedTabs: ["page"]
    },
    {
      mode:         RESOURCE_LINK,
      contentNames: ["resource", "page"],
      expectedTabs: [
        TabIds.Documents,
        TabIds.Videos,
        TabIds.Images,
        TabIds.Other,
        "page"
      ]
    }
  ])(
    "should render tabs based on contentNames. Case: $contentNames",
    async ({ mode, contentNames, expectedTabs }) => {
      const { wrapper } = await render({ mode, contentNames, expectedTabs })
      expect(wrapper.find(TabPane).map(pane => pane.prop("tabId"))).toEqual(
        expectedTabs
      )
    }
  )

  it.each([
    { modes: [RESOURCE_LINK, RESOURCE_EMBED] as const },
    { modes: [RESOURCE_EMBED, RESOURCE_LINK] as const }
  ])("initially displays resource listing for first tab", async ({ modes }) => {
    const { wrapper } = await render({ mode: modes[0] })
    const firstTab = wrapper.find(TabPane).first()
    // first tab has resource listing on initial render
    expect(firstTab.find(ResourcePickerListing).exists()).toBe(true)

    wrapper.setProps({ mode: modes[1] })

    // and first tab has resource listing after mode change
    const firstTabNewMode = wrapper.find(TabPane).first()
    expect(firstTabNewMode.find(ResourcePickerListing).exists()).toBe(true)
  })

  test("TabIds values are unique", () => {
    const uniqueTabIds = new Set(Object.values(TabIds))
    expect(Object.values(TabIds).length).toBe(uniqueTabIds.size)
  })

  it("should pass some basic props down to the dialog", async () => {
    const { wrapper } = await render()
    const dialog = wrapper.find("Dialog")
    expect(dialog.prop("open")).toBeTruthy()
    expect(dialog.prop("wrapClassName")).toBe("resource-picker-dialog")
  })

  it.each([
    {
      mode:       RESOURCE_LINK,
      attaching:  "linking",
      acceptText: "Add link"
    },
    {
      mode:       RESOURCE_EMBED,
      attaching:  "embedding",
      acceptText: "Embed resource"
    }
  ])(
    "should allow focusing and $attaching a resource, then close the dialog",
    async ({ mode, acceptText }) => {
      const { wrapper } = await render({ mode })
      // callback should be 'undefined' before resource is focused
      expect(wrapper.find(Dialog).prop("onAccept")).toBeUndefined()
      focusResource(wrapper, resource)

      expect(wrapper.find(Dialog).prop("acceptText")).toBe(acceptText)

      act(() => {
        wrapper.find(Dialog).prop("onAccept")?.()
      })

      wrapper.update()

      expect(insertEmbedStub.args[0]).toStrictEqual([
        resource.text_id,
        resource.title,
        mode
      ])
      expect(closeDialogStub.callCount).toBe(1)
    }
  )

  it.each([
    {
      index:        0,
      resourcetype: ResourceType.Document,
      contentType:  "resource",
      singleColumn: true
    },
    {
      index:        1,
      resourcetype: ResourceType.Video,
      contentType:  "resource",
      singleColumn: false
    },
    {
      index:        2,
      resourcetype: ResourceType.Image,
      contentType:  "resource",
      singleColumn: false
    },
    {
      index:        3,
      resourcetype: ResourceType.Other,
      contentType:  "resource",
      singleColumn: true
    },
    { index: 4, resourcetype: null, contentType: "page", singleColumn: true }
  ])(
    "passes the correct props to ResourcePickerListing when main tab $index is clicked",
    async ({ resourcetype, contentType, singleColumn, index }) => {
      const { wrapper } = await render({ mode: RESOURCE_LINK })
      act(() => {
        wrapper
          .find(NavLink)
          .at(index)
          .simulate("click")
      })
      wrapper.update()
      const listing = wrapper.find(ResourcePickerListing)
      expect(listing.prop("resourcetype")).toEqual(resourcetype)
      expect(listing.prop("contentType")).toBe(contentType)
      expect(listing.prop("singleColumn")).toBe(singleColumn)
    }
  )

  it("should pass filter string to picker, when filter is set", async () => {
    const setStub = helper.sandbox.stub()
    // @ts-ignore
    useDebouncedState.mockImplementation((initial, _ms) => {
      // this is just to un-debounce to make testing easier
      const [state, setState] = useState(initial)

      return [
        state,
        (update: any) => {
          setStub(update)
          setState(update)
        }
      ]
    })

    const { wrapper } = await render()

    act(() => {
      wrapper.find("input.filter-input").prop("onChange")!({
        // @ts-ignore
        currentTarget: { value: "new filter" }
      })
    })
    wrapper.update()

    expect(wrapper.find("ResourcePickerListing").prop("filter")).toEqual(
      "new filter"
    )
  })
})
