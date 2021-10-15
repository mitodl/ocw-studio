import React from "react"
import { shallow } from "enzyme"

import PublishStatusIndicator from "./PublishStatusIndicator"
import {
  PUBLISH_STATUS_ABORTED,
  PUBLISH_STATUS_ERRORED,
  PUBLISH_STATUS_NOT_STARTED,
  PUBLISH_STATUS_PENDING,
  PUBLISH_STATUS_SUCCEEDED
} from "../constants"

describe("PublishStatusIndicator", () => {
  [
    [PUBLISH_STATUS_NOT_STARTED, "Not started", "bg-secondary"],
    [PUBLISH_STATUS_PENDING, "In progress...", "bg-warning"],
    [PUBLISH_STATUS_ABORTED, "Aborted", "bg-danger"],
    [PUBLISH_STATUS_ERRORED, "Failed", "bg-danger"],
    [PUBLISH_STATUS_SUCCEEDED, "Succeeded", "bg-success"]
  ].forEach(([status, statusText, statusClass]) => {
    it(`renders for status=${status}`, () => {
      const wrapper = shallow(<PublishStatusIndicator status={status} />)
      expect(wrapper.text()).toContain(statusText)
      expect(
        wrapper.find(".publish-status-indicator").prop("className")
      ).toContain(statusClass)
    })
  })
})
