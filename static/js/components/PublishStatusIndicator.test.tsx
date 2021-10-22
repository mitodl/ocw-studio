import React from "react"
import { shallow } from "enzyme"

import PublishStatusIndicator from "./PublishStatusIndicator"
import { PublishStatuses } from "../constants"

describe("PublishStatusIndicator", () => {
  [
    [PublishStatuses.PUBLISH_STATUS_NOT_STARTED, "Not started", "bg-secondary"],
    [PublishStatuses.PUBLISH_STATUS_PENDING, "In progress...", "bg-warning"],
    [PublishStatuses.PUBLISH_STATUS_ABORTED, "Aborted", "bg-danger"],
    [PublishStatuses.PUBLISH_STATUS_ERRORED, "Failed", "bg-danger"],
    [PublishStatuses.PUBLISH_STATUS_SUCCEEDED, "Succeeded", "bg-success"]
  ].forEach(([status, statusText, statusClass]) => {
    it(`renders for status=${status}`, () => {
      const wrapper = shallow(
        <PublishStatusIndicator status={status as PublishStatuses} />
      )
      expect(wrapper.text()).toContain(statusText)
      expect(
        wrapper.find(".publish-status-indicator").prop("className")
      ).toContain(statusClass)
    })
  })
})
