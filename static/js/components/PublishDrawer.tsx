import React, { useState } from "react"
import { Modal, ModalBody, ModalHeader } from "reactstrap"
import { useStore } from "react-redux"
import { useMutation } from "redux-query-react"
import { requestAsync } from "redux-query"
import moment from "moment"
import { isEmpty } from "ramda"

import { websiteAction, websiteDetailRequest } from "../query-configs/websites"
import { isErrorStatusCode } from "../lib/util"
import PublishStatusIndicator from "./PublishStatusIndicator"

import { Website } from "../types/websites"

const STAGING = "staging"
const PRODUCTION = "production"

type Props = {
  visibility: boolean
  toggleVisibility: () => void
  website: Website
}
export default function PublishDrawer(props: Props): JSX.Element {
  const { visibility, toggleVisibility, website } = props

  const [{ isPending: previewIsPending }, previewWebsite] = useMutation(() =>
    websiteAction(website.name, "preview")
  )
  const [{ isPending: publishIsPending }, publishWebsite] = useMutation(() =>
    websiteAction(website.name, "publish")
  )
  const store = useStore()
  const [publishOption, setPublishOption] = useState<string>(STAGING)
  const [errorStaging, setErrorStaging] = useState<boolean>(false)
  const [errorProduction, setErrorProduction] = useState<boolean>(false)

  const onPreview = async () => {
    setErrorStaging(false)
    if (previewIsPending) {
      return
    }
    const response = await previewWebsite()
    if (!response) {
      return
    } else {
      if (isErrorStatusCode(response.status)) {
        setErrorStaging(true)
      } else {
        // refresh
        toggleVisibility()
        await store.dispatch(requestAsync(websiteDetailRequest(website.name)))
      }
    }
  }

  const onPublish = async () => {
    setErrorProduction(false)
    if (publishIsPending) {
      return
    }
    const response = await publishWebsite()
    if (!response) {
      return
    } else {
      if (isErrorStatusCode(response.status)) {
        setErrorProduction(true)
      } else {
        // refresh
        toggleVisibility()
        store.dispatch(requestAsync(websiteDetailRequest(website.name)))
      }
    }
  }

  const renderOption = (option: string) => {
    const isStaging = option === STAGING
    const label = isStaging ? "Staging" : "Production"
    const publish = isStaging ? onPreview : onPublish
    const error = isStaging ? errorStaging : errorProduction
    const siteUrl = isStaging ? website.draft_url : website.live_url
    const publishDate = isStaging ?
      website.draft_publish_date :
      website.publish_date
    const hasUnpublishedChanges = isStaging ?
      website.has_unpublished_draft :
      website.has_unpublished_live
    const publishStatus = isStaging ?
      website.draft_publish_status :
      website.live_publish_status

    return (
      <div className="publish-option my-2">
        <div className="d-flex flex-direction-row align-items-center">
          <input
            type="radio"
            id={`publish-${option}`}
            value={option}
            checked={publishOption === option}
            onChange={() => setPublishOption(option)}
          />{" "}
          <label htmlFor={`publish-${option}`}>{label}</label>
        </div>
        {publishOption === option ? (
          <div className="publish-option-description">
            <a href={siteUrl} target="_blank" rel="noreferrer">
              {siteUrl}
            </a>
            <br />
            Last updated:{" "}
            {publishDate ?
              moment(publishDate).format("dddd, MMMM D h:mma ZZ") :
              "never published"}
            <br />
            {hasUnpublishedChanges ? (
              <>
                <strong>You have unpublished changes.</strong>
                <br />
              </>
            ) : null}
            {error ? (
              <>
                <strong className="text-danger">
                  We apologize, there was an error publishing the site. Please
                  try again in a few minutes.
                </strong>
                <br />
              </>
            ) : null}
            <button
              onClick={publish}
              disabled={!hasUnpublishedChanges}
              className="btn btn-publish cyan-button-outline d-flex flex-direction-row align-items-center"
            >
              Publish
            </button>
            <PublishStatusIndicator status={publishStatus} />
          </div>
        ) : null}
      </div>
    )
  }

  return (
    <Modal isOpen={visibility} toggle={toggleVisibility} modalClassName="right">
      <ModalHeader toggle={toggleVisibility}>Publish your site</ModalHeader>
      <ModalBody>
        {renderOption(STAGING)}
        {website.is_admin ? renderOption(PRODUCTION) : null}
        {website.content_warnings && !isEmpty(website.content_warnings) ? (
          <div className="publish-warnings pt-2">
            <strong className="text-danger">
              This site is missing information that could affect publishing
              output.
            </strong>
            <ul className="text-danger">
              {website.content_warnings.map((warning: string, idx: number) => (
                <li key={idx}>{warning}</li>
              ))}
            </ul>
          </div>
        ) : null}
      </ModalBody>
    </Modal>
  )
}
