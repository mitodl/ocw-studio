import React from "react"
import { Button, Modal, ModalBody, ModalFooter, ModalHeader } from "reactstrap"

export interface Props {
  open: boolean
  toggleModal: () => void
  onCancel?: () => void
  onAccept?: () => void
  acceptText?: string
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
    toggleModal,
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
    <button className="close" onClick={toggleModal}>
      &times;
    </button>
  )

  return (
    <Modal
      isOpen={open}
      toggle={toggleModal}
      wrapClassName={wrapClassName}
      modalClassName={modalClassName}
      backdropClassName={backdropClassName}
      contentClassName={contentClassName}
    >
      <ModalHeader toggle={toggleModal} close={closeBtn}>
        {headerContent}
      </ModalHeader>
      <ModalBody>{bodyContent}</ModalBody>
      <ModalFooter>
        {onAccept ? (
          <Button color="primary" onClick={onAccept}>
            {acceptText || "OK"}
          </Button>
        ) : null}
        <Button color="secondary" onClick={onCancel || toggleModal}>
          {cancelText || "Cancel"}
        </Button>
      </ModalFooter>
    </Modal>
  )
}
