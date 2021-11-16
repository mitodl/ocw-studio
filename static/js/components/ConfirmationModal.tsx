import React from "react"
import { Prompt } from "react-router"
import { useBeforeunload } from "react-beforeunload"

import BasicModal from "./BasicModal"

interface Props {
  dirty: boolean
  confirmationModalVisible: boolean
  setConfirmationModalVisible: (visible: boolean) => void
  dismiss: () => void
}
export default function ConfirmationModal(props: Props): JSX.Element {
  const {
    dirty,
    confirmationModalVisible,
    setConfirmationModalVisible,
    dismiss
  } = props

  // Note that this text won't show up at least on Chrome and Firefox. They use their own similar messages.
  useBeforeunload(() =>
    dirty ?
      "You have unsaved changes. Are you sure you want to leave this page?" :
      null
  )

  return (
    <>
      <Prompt
        message={() =>
          dirty ?
            "You have unsaved changes. Are you sure you want to discard your changes?" :
            true
        }
      />
      <BasicModal
        isVisible={confirmationModalVisible}
        hideModal={() => setConfirmationModalVisible(false)}
        className=""
        title="Discard changes"
      >
        {() => (
          <div className="d-flex flex-column align-items-center">
            <p>
              You have unsaved changes. Are you sure you want to discard your
              changes?
            </p>
            <div className="d-flex flex-direction-row">
              <button className="discard mr-5" onClick={dismiss}>
                Discard changes
              </button>
              <button
                className="cancel"
                onClick={() => setConfirmationModalVisible(false)}
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </BasicModal>
    </>
  )
}
