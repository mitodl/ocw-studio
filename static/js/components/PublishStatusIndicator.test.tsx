import React from "react"
import { shallow } from "enzyme"

import PublishStatusIndicator from "./PublishStatusIndicator"
import { PublishStatus } from "../constants"

describe("PublishStatusIndicator", () => {
  [
    [PublishStatus.NotStarted, "Not started", "bg-secondary"],
    [PublishStatus.Pending, "In progress...", "bg-warning"],
    [PublishStatus.Aborted, "Aborted", "bg-danger"],
    [PublishStatus.Errored, "Failed", "bg-danger"],
    [PublishStatus.Success, "Succeeded", "bg-success"]
  ].forEach(([status, statusText, statusClass]) => {
    it(`renders for status=${status}`, () => {
      const wrapper = shallow(
        <PublishStatusIndicator status={status as PublishStatus} />
      )
      expect(wrapper.text()).toContain(statusText)
      expect(
        wrapper.find(".publish-status-indicator").prop("className")
      ).toContain(statusClass)
    })
  })
})
