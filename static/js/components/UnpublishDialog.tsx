import React, { useState } from "react"
import { Button, Modal, ModalBody, ModalHeader, ModalFooter } from "reactstrap"
import { useMutation } from "redux-query-react"

import { websiteUnpublishAction } from "../query-configs/websites"
import { isErrorStatusCode } from "../lib/util"

export default function UnpublishDialog(props: {
  websiteName: string
  successCallback: () => void
  closeDialog: () => void
}): JSX.Element {
  const { websiteName, successCallback, closeDialog } = props
  const [isSiteUnpublished, setIsSiteUnpublished] = useState(false)
  const [siteUnpublishedMsg, setSiteUnpublishedMsg] = useState("")
  const [error, setError] = useState("")

  const [{ isPending }, unpublishPost] = useMutation(() =>
    websiteUnpublishAction(websiteName, "POST")
  )
  const handleUnpublishPost = async () => {
    if (isPending) {
      return
    }

    const response = await unpublishPost()
    if (!response) {
      return
    } else {
      if (isErrorStatusCode(response.status)) {
        setError(
          `Something went wrong while unpublishing the website: ${JSON.stringify(
            response.body
          )}`
        )
      } else {
        setSiteUnpublishedMsg(response.body)
        setIsSiteUnpublished(true)
        successCallback()
      }
    }
  }

  const closeBtn = (
    <button className="close" onClick={closeDialog}>
      &times;
    </button>
  )

  if (!isSiteUnpublished) {
    return (
      <Modal isOpen={true} toggle={closeDialog}>
        <ModalHeader toggle={closeDialog} close={closeBtn}>
          Confirmation required
        </ModalHeader>
        <ModalBody>
          {!error ? (
            <div>Are you sure you want to unpublish <b>{websiteName}</b>?</div>
          ) : (
            <div className="form-error">{error}</div>
          )}
        </ModalBody>
        <ModalFooter>
          <Button color="secondary" onClick={closeDialog}>
            Cancel
          </Button>
          <Button className="cyan-button" onClick={handleUnpublishPost}>
            Confirm
          </Button>
        </ModalFooter>
      </Modal>
    )
  }
  return (
    <Modal isOpen={true} toggle={closeDialog}>
      <ModalBody>{siteUnpublishedMsg}</ModalBody>
      <ModalFooter>
        <Button color="secondary" onClick={closeDialog}>
          Close
        </Button>
      </ModalFooter>
    </Modal>
  )
}
