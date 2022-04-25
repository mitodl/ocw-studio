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
  //
  ;[
    [GoogleDriveSyncStatuses.SYNC_STATUS_PROCESSING, []],
    [GoogleDriveSyncStatuses.SYNC_STATUS_PENDING, []],
    [GoogleDriveSyncStatuses.SYNC_STATUS_COMPLETE, []],
    [GoogleDriveSyncStatuses.SYNC_STATUS_ERRORS, ["error1", "error2"]],
    [GoogleDriveSyncStatuses.SYNC_STATUS_FAILED, ["total failure"]]
  ].forEach(([status, syncErrors]) => {
    describe("sync status drawer", () => {
      beforeEach(() => {
        website = {
          ...makeWebsiteDetail(),
          sync_status: status as GoogleDriveSyncStatuses,
          sync_errors: syncErrors as Array<string>,
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
          // @ts-ignore
          statusDiv.prop("onClick")({ preventDefault: helper.sandbox.stub() })
        })
        wrapper.update()
        const drawer = wrapper.find("BasicModal").at(0)
        expect(drawer.prop("isVisible")).toBe(true)
        //@ts-ignore
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
})
