import React, { useState, useEffect } from "react"
import { Button, Modal, ModalBody, ModalHeader, ModalFooter } from "reactstrap"
import { useMutation } from "redux-query-react"
import ReactJson from "react-json-view"

import { websiteUnpublishAction} from "../query-configs/websites"
import { isErrorStatusCode } from "../lib/util"


export default function UnpublishDialog(props: {
  websiteName: string,
  closeDialog: () => void
  }): JSX.Element {

  const { websiteName, closeDialog } = props
  const [siteDependencies, setSiteDependencies] = useState(null)
  const [isSiteUnpublished, setIsSiteUnpublished] = useState(false)
  const [siteUnpublishedMsg, setSiteUnpublishedMsg] = useState("")
  const [error, setError] = useState("")

  const handleUnpublishGet = async () => {
    
    const [ { isPending }, unpublishGet ] = useMutation(() => websiteUnpublishAction(websiteName, "GET"))
    
    if (isPending) {
      return
    }
    const response = await unpublishGet()
    if (!response) {
      return
    } else {
      if (isErrorStatusCode(response.status)) {
        setError(`Something went wrong while fetching website dependencies. ${response.body}`)
      } else {
        setSiteDependencies(response.body.site_dependencies)
      }
    }
  }

  const handleUnpublishPost = async () => {
    const [ { isPending }, unpublishPost ] = useMutation(() => websiteUnpublishAction(websiteName, "POST"))
    
    if (isPending) {
      return
    }

    const response = await unpublishPost()
    if (!response) {
      return
    } else {
      if (isErrorStatusCode(response.status)) {
        setError(`Something went wrong while unpublishing the website. ${response.body}`)
      } else {
          setSiteUnpublishedMsg(response.body)
          setIsSiteUnpublished(true)
      }
    }
  }

  useEffect(() => {
    handleUnpublishGet()
  }, []);

  const closeBtn = (
    <button className="close" onClick={closeDialog}>
      &times;
    </button>
  )

  if(!isSiteUnpublished){
    return (
      <Modal
        isOpen={true}
        toggle={closeDialog}
        size="lg"
      >
        <ModalHeader toggle={closeDialog} close={closeBtn}>
          Are you sure you want to unpublish this site?
        </ModalHeader>
        <ModalBody>
          {!error ? 
            <div>
              {!siteDependencies ? "Loading Dependencies..." :
                <ReactJson
                  name={`Dependecies of ${websiteName}'`}
                  src={siteDependencies}
                  iconStyle="square"
                  displayDataTypes={false}
                  collapsed={1}
                  enableClipboard={false} />}
            </div>
          : <div className="form-error">{error}</div> }
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
    <Modal
      isOpen={true}
      toggle={closeDialog}
    >
      <ModalBody>
        {siteUnpublishedMsg}
      </ModalBody>
      <ModalFooter>
        <Button color="secondary" onClick={closeDialog}>
          Close
        </Button>
      </ModalFooter>
    </Modal> 
  )
}
