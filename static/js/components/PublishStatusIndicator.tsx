import * as React from "react"

import {
  PUBLISH_STATUS_ABORTED,
  PUBLISH_STATUS_ERRORED,
  PUBLISH_STATUS_NOT_STARTED,
  PUBLISH_STATUS_PENDING,
  PUBLISH_STATUS_SUCCEEDED
} from "../constants"

const publishStatusMessage = (status: string): string => {
  switch (status) {
  case PUBLISH_STATUS_NOT_STARTED:
    return "Not started"
  case PUBLISH_STATUS_PENDING:
    return "In progress..."
  case PUBLISH_STATUS_ABORTED:
    return "Aborted"
  case PUBLISH_STATUS_ERRORED:
    return "Failed"
  case PUBLISH_STATUS_SUCCEEDED:
    return "Succeeded"
  default:
    return ""
  }
}

const publishStatusIndicatorClass = (status: string): string => {
  switch (status) {
  case PUBLISH_STATUS_NOT_STARTED:
    return "bg-secondary"
  case PUBLISH_STATUS_PENDING:
    return "bg-warning"
  case PUBLISH_STATUS_ABORTED:
  case PUBLISH_STATUS_ERRORED:
    return "bg-danger"
  case PUBLISH_STATUS_SUCCEEDED:
    return "bg-success"
  default:
    return ""
  }
}

interface Props {
  status: string | null
}
export default function PublishStatusIndicator(
  props: Props
): JSX.Element | null {
  const { status } = props
  return status ? (
    <div className="d-flex flex-direction-row align-items-center">
      <div
        className={`publish-status-indicator ${publishStatusIndicatorClass(
          status
        )}`}
      />
      {publishStatusMessage(status)}
    </div>
  ) : null
}
