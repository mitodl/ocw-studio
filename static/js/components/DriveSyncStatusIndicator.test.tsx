import React from "react"
import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import moment from "moment"

import IntegrationTestHelper from "../testing_utils/IntegrationTestHelper"
import DriveSyncStatusIndicator from "./DriveSyncStatusIndicator"
import { GoogleDriveSyncStatuses } from "../constants"
import { makeWebsiteDetail } from "../util/factories/websites"
import { Website } from "../types/websites"

describe("DriveSyncStatusIndicator", () => {
  let helper: IntegrationTestHelper, website: Website

  beforeEach(() => {
    helper = new IntegrationTestHelper()
  })

  afterEach(() => {
    document.body.innerHTML = ""
  })

  describe.each([
    {
      status: GoogleDriveSyncStatuses.SYNC_STATUS_PROCESSING,
      syncErrors: [],
    },
    {
      status: GoogleDriveSyncStatuses.SYNC_STATUS_PENDING,
      syncErrors: [],
    },
    {
      status: GoogleDriveSyncStatuses.SYNC_STATUS_COMPLETE,
      syncErrors: [],
    },
    {
      status: GoogleDriveSyncStatuses.SYNC_STATUS_ERRORS,
      syncErrors: ["error1", "error2"],
    },
    {
      status: GoogleDriveSyncStatuses.SYNC_STATUS_FAILED,
      syncErrors: ["total failure"],
    },
  ])("sync status drawer", ({ status, syncErrors }) => {
    beforeEach(() => {
      website = {
        ...makeWebsiteDetail(),
        sync_status: status,
        sync_errors: syncErrors,
        synced_on: "2021-01-01",
      }
    })

    it(`renders for status=${status}`, () => {
      helper.render(<DriveSyncStatusIndicator website={website} />)
      expect(screen.getByText(new RegExp(status))).toBeInTheDocument()
      const statusIndicator = document.querySelector(".status-indicator")
      expect(statusIndicator?.className).toContain(status.toLowerCase())
    })

    it(`shows details with sync date and ${syncErrors.length} errors in side drawer`, async () => {
      const user = userEvent.setup()
      helper.render(<DriveSyncStatusIndicator website={website} />)

      expect(
        screen.queryByText("Google Drive Sync Details"),
      ).not.toBeInTheDocument()

      const statusDiv = screen.getByText(/Sync status:/)
      await user.click(statusDiv)

      await screen.findByText("Google Drive Sync Details")

      syncErrors.forEach((error: string) => {
        expect(screen.getByText(error)).toBeInTheDocument()
      })

      const errorItems = document.querySelectorAll("li")
      expect(errorItems.length).toBe(syncErrors.length)

      if (syncErrors.length === 0) {
        expect(
          screen.getByText(/The latest Google Drive sync was successful./),
        ).toBeInTheDocument()
      }

      const formattedDate = moment(website.synced_on).format(
        "dddd, MMMM D h:mma ZZ",
      )
      const syncTimeElement = document.querySelector(".sync-time")
      expect(syncTimeElement).toBeInTheDocument()
      expect(syncTimeElement?.textContent).toContain(formattedDate)

      const closeButton = screen.getByLabelText("Close")
      await user.click(closeButton)

      await waitFor(() => {
        expect(
          screen.queryByText("Google Drive Sync Details"),
        ).not.toBeInTheDocument()
      })
    })
  })
})
