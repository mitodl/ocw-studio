import { act } from "react-dom/test-utils"
import moment from "moment"

import IntegrationTestHelper, {
  TestRenderer
} from "../util/integration_test_helper_old"
import DriveSyncStatusIndicator from "./DriveSyncStatusIndicator"
import { GoogleDriveSyncStatuses } from "../constants"
import { makeWebsiteDetail } from "../util/factories/websites"
import { Website } from "../types/websites"

describe("DriveSyncStatusIndicator", () => {
  let helper: IntegrationTestHelper, render: TestRenderer, website: Website
  beforeEach(() => {
    helper = new IntegrationTestHelper()
  })

  afterEach(() => {
    helper.cleanup()
  })

  describe.each([
    {
      status:     GoogleDriveSyncStatuses.SYNC_STATUS_PROCESSING,
      syncErrors: []
    },
    {
      status:     GoogleDriveSyncStatuses.SYNC_STATUS_PENDING,
      syncErrors: []
    },
    {
      status:     GoogleDriveSyncStatuses.SYNC_STATUS_COMPLETE,
      syncErrors: []
    },
    {
      status:     GoogleDriveSyncStatuses.SYNC_STATUS_ERRORS,
      syncErrors: ["error1", "error2"]
    },
    {
      status:     GoogleDriveSyncStatuses.SYNC_STATUS_FAILED,
      syncErrors: ["total failure"]
    }
  ])("sync status drawer", ({ status, syncErrors }) => {
    beforeEach(() => {
      website = {
        ...makeWebsiteDetail(),
        sync_status: status,
        sync_errors: syncErrors,
        synced_on:   "2021-01-01"
      }
      render = helper.configureRenderer(DriveSyncStatusIndicator, {
        website
      })
    })

    afterEach(() => {
      helper.cleanup()
    })

    it(`renders for status=${status}`, async () => {
      const { wrapper } = await render()
      expect(wrapper.text()).toContain(status)
      expect(wrapper.find(".status-indicator").prop("className")).toContain(
        status.toString().toLowerCase()
      )
    })

    it(`shows details with sync date and ${syncErrors.length} errors in side drawer`, async () => {
      const { wrapper } = await render()
      expect(wrapper.find("BasicModal").prop("isVisible")).toBe(false)

      const statusDiv = wrapper.find(".sync-status")
      act(() => {
        // @ts-expect-error Not mocking the whole event
        statusDiv.prop("onClick")({ preventDefault: helper.sandbox.stub() })
      })
      wrapper.update()
      const drawer = wrapper.find("BasicModal").at(0)
      expect(drawer.prop("isVisible")).toBe(true)

      syncErrors.forEach((error: string, idx: number) => {
        expect(
          drawer
            .find("li")
            .at(idx)
            .text()
        ).toBe(error)
      })
      expect(drawer.find("li").length).toBe(syncErrors.length)
      if (syncErrors.length === 0) {
        expect(
          drawer
            .find(".sync-success")
            .at(0)
            .text()
        ).toContain("The latest Google Drive sync was successful.")
      }
      expect(drawer.find(".sync-time").text()).toContain(
        moment(website.synced_on).format("dddd, MMMM D h:mma ZZ")
      )
    })
  })
})
