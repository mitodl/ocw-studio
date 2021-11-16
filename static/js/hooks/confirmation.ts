import { useCallback, useState } from "react"

interface Args {
  dirty: boolean
  setDirty: (dirty: boolean) => void
  close?: () => void
}
interface ReturnValue {
  confirmationModalVisible: boolean
  setConfirmationModalVisible: (visible: boolean) => void
  conditionalClose: (skipConfirmation: boolean) => void
}

/**
 * Manages some state for a confirmation modal. Meant to be used with <ConfirmationModal />
 *
 * The calling component passes in dirty/setDirty to manage this state. The component may also optionally
 * pass in 'close' to close the content drawer or otherwise hide any state in the containing UI.
 *
 * This returns confirmationModalVisible/setConfirmationModalVisible to let the calling component manage that state,
 * and also conditionalClose. conditionalClose will either show a confirmation modal, or skip it and call 'close'.
 */
export default function useConfirmation({
  dirty,
  setDirty,
  close
}: Args): ReturnValue {
  const [confirmationModalVisible, setConfirmationModalVisible] = useState<
    boolean
  >(false)

  // User indicates a desire to close panel. If dirty, show confirmation dialog, else just close panel.
  // skipConfirmation may be true if user clicked 'save' or if user clicked 'discard changes'
  const conditionalClose = useCallback(
    (skipConfirmation: boolean): void => {
      if (dirty && !skipConfirmation) {
        setConfirmationModalVisible(true)
      } else {
        if (close) {
          close()
        }
        setConfirmationModalVisible(false)
        setDirty(false)
      }
    },
    [dirty, setDirty, setConfirmationModalVisible, close]
  )

  return {
    setConfirmationModalVisible,
    confirmationModalVisible,
    conditionalClose
  }
}
