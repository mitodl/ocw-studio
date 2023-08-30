import * as React from "react"

import { PublishStatus } from "../constants"

const publishStatusMessage = (status: PublishStatus): string => {
  switch (status) {
    case PublishStatus.NotStarted:
      return "Not started"
    case PublishStatus.Pending:
    case PublishStatus.Started:
      return "In progress..."
    case PublishStatus.Aborted:
      return "Aborted"
    case PublishStatus.Errored:
      return "Failed"
    case PublishStatus.Success:
      return "Succeeded"
    default:
      return ""
  }
}

const publishStatusIndicatorClass = (status: PublishStatus): string => {
  switch (status) {
    case PublishStatus.NotStarted:
      return "bg-secondary"
    case PublishStatus.Pending:
    case PublishStatus.Started:
      return "bg-warning"
    case PublishStatus.Aborted:
    case PublishStatus.Errored:
      return "bg-danger"
    case PublishStatus.Success:
      return "bg-success"
    default:
      return ""
  }
}

interface Props {
  status: PublishStatus | null
}
export default function PublishStatusIndicator(
  props: Props,
): JSX.Element | null {
  const { status } = props
  return status ? (
    <div className="d-flex flex-direction-row align-items-center">
      <div
        className={`publish-status-indicator ${publishStatusIndicatorClass(
          status,
        )}`}
      />
      {publishStatusMessage(status)}
    </div>
  ) : null
}
