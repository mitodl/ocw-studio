import React from "react"
import { Button, Modal, ModalBody, ModalFooter, ModalHeader } from "reactstrap"

export interface Props {
  open: boolean
  onCancel: () => void
  onAccept?: () => void
  acceptText?: string
  altAcceptText?: string
  cancelText?: string
  headerContent: JSX.Element | string
  bodyContent: JSX.Element | string
  wrapClassName?: string
  modalClassName?: string
  backdropClassName?: string
  contentClassName?: string
}

export default function Dialog(props: Props): JSX.Element | null {
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
          <Button color="primary" onClick={onAccept}>
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
