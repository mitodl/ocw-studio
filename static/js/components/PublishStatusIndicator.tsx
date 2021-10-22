import * as React from "react"

import { PublishStatuses } from "../constants"

const publishStatusMessage = (status: PublishStatuses): string => {
  switch (status) {
  case PublishStatuses.PUBLISH_STATUS_NOT_STARTED:
    return "Not started"
  case PublishStatuses.PUBLISH_STATUS_PENDING:
    return "In progress..."
  case PublishStatuses.PUBLISH_STATUS_ABORTED:
    return "Aborted"
  case PublishStatuses.PUBLISH_STATUS_ERRORED:
    return "Failed"
  case PublishStatuses.PUBLISH_STATUS_SUCCEEDED:
    return "Succeeded"
  default:
    return ""
  }
}

const publishStatusIndicatorClass = (status: PublishStatuses): string => {
  switch (status) {
  case PublishStatuses.PUBLISH_STATUS_NOT_STARTED:
    return "bg-secondary"
  case PublishStatuses.PUBLISH_STATUS_PENDING:
    return "bg-warning"
  case PublishStatuses.PUBLISH_STATUS_ABORTED:
  case PublishStatuses.PUBLISH_STATUS_ERRORED:
    return "bg-danger"
  case PublishStatuses.PUBLISH_STATUS_SUCCEEDED:
    return "bg-success"
  default:
    return ""
  }
}

interface Props {
  status: PublishStatuses | null
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
