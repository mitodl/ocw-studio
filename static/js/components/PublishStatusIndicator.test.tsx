import React from "react"
import { render, screen } from "@testing-library/react"

import PublishStatusIndicator from "./PublishStatusIndicator"
import { PublishStatus } from "../constants"

describe("PublishStatusIndicator", () => {
  ;[
    [PublishStatus.NotStarted, "Not started", "bg-secondary"],
    [PublishStatus.Pending, "In progress...", "bg-warning"],
    [PublishStatus.Aborted, "Aborted", "bg-danger"],
    [PublishStatus.Errored, "Failed", "bg-danger"],
    [PublishStatus.Success, "Succeeded", "bg-success"],
  ].forEach(([status, statusText, statusClass]) => {
    it(`renders for status=${status}`, () => {
      const { container } = render(
        <PublishStatusIndicator status={status as PublishStatus} />,
      )
      expect(screen.getByText(statusText as string)).toBeInTheDocument()
      const indicator = container.querySelector(".publish-status-indicator")
      expect(indicator).toHaveClass(statusClass as string)
    })
  })
})
