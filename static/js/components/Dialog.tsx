import React from "react"
import {
  Button,
  Modal,
  ModalBody,
  ModalFooter,
  ModalHeader,
  ModalProps
} from "reactstrap"

export interface Props {
  open: boolean
  onCancel: () => void
  onAccept?: () => void
  acceptText?: string
  altAcceptText?: string
  cancelText?: string
  headerContent: React.ReactNode
  bodyContent: React.ReactNode
  wrapClassName?: ModalProps["wrapClassName"]
  modalClassName?: ModalProps["modalClassName"]
  backdropClassName?: ModalProps["backdropClassName"]
  contentClassName?: ModalProps["contentClassName"]
}

const Dialog: React.FC<Props> = props => {
  const {
    open,
    headerContent,
    bodyContent,
    onAccept,
    onCancel,
    acceptText,
    cancelText,
    wrapClassName,
    modalClassName,
    backdropClassName,
    contentClassName
  } = props

  const closeBtn = (
    <button className="close" onClick={onCancel}>
      &times;
    </button>
  )

  return (
    <Modal
      isOpen={open}
      toggle={onCancel}
      wrapClassName={wrapClassName}
      modalClassName={modalClassName}
      backdropClassName={backdropClassName}
      contentClassName={contentClassName}
    >
      <ModalHeader toggle={onCancel} close={closeBtn}>
        {headerContent}
      </ModalHeader>
      <ModalBody>{bodyContent}</ModalBody>
      <ModalFooter>
        {onAccept ? (
          <Button className="cyan-button" onClick={onAccept}>
            {acceptText || "OK"}
          </Button>
        ) : null}
        <Button color="secondary" onClick={onCancel}>
          {cancelText || "Cancel"}
        </Button>
      </ModalFooter>
    </Modal>
  )
}

export default Dialog
