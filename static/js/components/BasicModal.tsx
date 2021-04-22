import React from "react"
import { Modal, ModalBody, ModalHeader } from "reactstrap"

interface PassDownProps {
  hideModal: () => void
}

export default function BasicModal(props: {
  isVisible: boolean
  hideModal: () => void
  className: string | null
  title: string | null
  children: (props: PassDownProps) => JSX.Element | null
}): JSX.Element | null {
  const { children, isVisible, hideModal, className, title } = props

  return (
    <div>
      <Modal
        isOpen={isVisible}
        toggle={hideModal}
        modalClassName={className ?? ""}
      >
        <ModalHeader toggle={hideModal}>{title}</ModalHeader>
        <ModalBody>{children({ hideModal })}</ModalBody>
      </Modal>
    </div>
  )
}
