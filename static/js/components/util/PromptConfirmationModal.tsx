import React, {
  useState,
  useCallback,
  useImperativeHandle,
  forwardRef,
} from "react"
import { Modal, ModalBody, ModalFooter, ModalHeader } from "reactstrap"

// Type definition for the confirmation function
// This matches the old getUserConfirmation signature from BrowserRouter
export type GetUserConfirmation = (
  message: string,
  callback: (ok: boolean) => void,
) => void

/**
 * This is a confirmation modal to be used with react-router's <Prompt />.
 * By default, react-router's <Prompt /> component uses window.confirm which is
 * not very customizable.
 *
 * Note: With history v5.0.0+, getUserConfirmation was removed from BrowserRouter.
 * This modal can still be used with React Router's <Prompt> component for
 * custom confirmation dialogs.
 */
const PromptConfirmationModal = (
  _props: unknown,
  ref: React.Ref<GetUserConfirmation>,
) => {
  const [isOpen, setIsOpen] = useState(false)
  const [message, setMessage] = useState("This should never be seen.")
  const [onCancel, setOnCancel] = useState(() => () => setIsOpen(false))
  const [onConfirm, setOnConfirm] = useState(() => () => setIsOpen(false))
  const getUserConfirmation = useCallback<GetUserConfirmation>((msg, cb) => {
    setMessage(msg)
    setIsOpen(true)
    const makeResponse = (ok: boolean) => () => {
      cb(ok)
      setIsOpen(false)
    }
    setOnCancel(() => makeResponse(false))
    setOnConfirm(() => makeResponse(true))
  }, [])
  useImperativeHandle(ref, () => getUserConfirmation, [getUserConfirmation])
  return (
    <Modal isOpen={isOpen}>
      <ModalHeader>Are you sure?</ModalHeader>
      <ModalBody>{message}</ModalBody>
      <ModalFooter>
        <button className="btn btn-secondary" onClick={onCancel}>
          Cancel
        </button>
        <button className="btn btn-outline-danger" onClick={onConfirm}>
          Confirm
        </button>
      </ModalFooter>
    </Modal>
  )
}

export default forwardRef(PromptConfirmationModal)
