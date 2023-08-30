import React, { MouseEvent as ReactMouseEvent, useState } from "react"
import moment from "moment"

import BasicModal from "./BasicModal"
import { Website } from "../types/websites"

export default function DriveSyncStatusIndicator(props: {
  website: Website
}): JSX.Element | null {
  const { website } = props

  const [syncStatusModalState, setSyncStatusModalState] = useState({
    isVisible: false,
  })
  const toggleSyncStatusModal = () =>
    setSyncStatusModalState({
      isVisible: !syncStatusModalState.isVisible,
    })
  const onShowSyncDetails = async (
    event: ReactMouseEvent<HTMLDivElement | HTMLButtonElement, MouseEvent>,
  ) => {
    event.preventDefault()
    toggleSyncStatusModal()
  }

  return (
    <>
      <BasicModal
        isVisible={syncStatusModalState.isVisible}
        hideModal={() => toggleSyncStatusModal()}
        title="Google Drive Sync Details"
        className="right"
      >
        {(_) => (
          <div className="m-2">
            <div className="pb-2 sync-time">
              Last run at{" "}
              {moment(website.synced_on).format("dddd, MMMM D h:mma ZZ")}
            </div>
            {website.sync_errors && website.sync_errors.length > 0 ? (
              <ul>
                {website.sync_errors.map((error: string, idx: number) => (
                  <li key={idx} className="py-3 listing-result form-error">
                    {error}
                  </li>
                ))}
              </ul>
            ) : (
              <div className="sync-success">
                The latest Google Drive sync was successful.
              </div>
            )}
          </div>
        )}
      </BasicModal>
      {website.sync_status ? (
        <div className="d-flex ml-2 sync-status" onClick={onShowSyncDetails}>
          <div
            className={`status-indicator ${website.sync_status.toLowerCase()} mr-1 mt-1`}
          ></div>
          <div>Sync status: {website.sync_status}</div>
        </div>
      ) : null}
    </>
  )
}
