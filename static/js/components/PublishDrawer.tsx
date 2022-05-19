import React, { useState } from "react"
import { Modal, ModalBody, ModalHeader } from "reactstrap"
import { useMutation } from "redux-query-react"
import { requestAsync } from "redux-query"
import moment from "moment"
import { isEmpty } from "ramda"

import {
  websitePublishAction,
  websiteDetailRequest,
  WebsitePublishPayload
} from "../query-configs/websites"
import { isErrorStatusCode } from "../lib/util"
import PublishStatusIndicator from "./PublishStatusIndicator"

import { Website } from "../types/websites"
import PublishForm, {
  OnSubmitPublish,
  SiteFormValues
} from "./forms/PublishForm"
import { PublishingEnv, PublishStatus } from "../constants"
import { useAppDispatch } from "../hooks/redux"

interface PublishingOptionProps {
  website: Website
  publishingEnv: PublishingEnv
  selected: boolean
  onSelect: (publishingEnv: PublishingEnv) => void
  onPublishSuccess: () => void
}
interface PublishingInfo {
  date: string | null
  status: PublishStatus | null
  hasUnpublishedChanges: boolean
  envLabel: string
}

const getPublishingInfo = (
  website: Website,
  publishingEnv: PublishingEnv
): PublishingInfo => {
  if (publishingEnv === PublishingEnv.Staging) {
    return {
      envLabel:              "Staging",
      date:                  website.draft_publish_date,
      status:                website.draft_publish_status,
      hasUnpublishedChanges: website.has_unpublished_draft
    }
  }
  if (publishingEnv === PublishingEnv.Production) {
    return {
      envLabel:              "Production",
      date:                  website.publish_date,
      status:                website.live_publish_status,
      hasUnpublishedChanges: website.has_unpublished_live
    }
  }
  throw new Error("Invalid PublishingEnv")
}

const PublishingOption: React.FC<PublishingOptionProps> = props => {
  const { publishingEnv, selected, onSelect, website, onPublishSuccess } = props
  const publishingInfo = getPublishingInfo(website, publishingEnv)

  const [
    { isPending },
    publish
  ] = useMutation((payload: WebsitePublishPayload) =>
    websitePublishAction(website.name, publishingEnv, payload)
  )

  const handlePublish: OnSubmitPublish = async (payload, helpers) => {
    if (isPending) {
      return
    }
    const response = await publish(payload)
    if (!response) {
      return
    } else {
      if (isErrorStatusCode(response.status)) {
        const errorBody: Partial<SiteFormValues> | undefined = response.body
        const errors = {
          url_path: errorBody?.url_path
        }
        helpers.setErrors(errors)
        helpers.setStatus(
          "We apologize, there was a problem publishing your site."
        )
      } else {
        onPublishSuccess()
      }
    }
  }

  return (
    <div className="publish-option my-2">
      <div className="d-flex flex-direction-row align-items-center">
        <input
          type="radio"
          id={`publish-${publishingEnv}`}
          value={publishingEnv}
          checked={selected}
          onChange={e => {
            if (e.target.checked) {
              onSelect(publishingEnv)
            }
          }}
        />{" "}
        <label htmlFor={`publish-${publishingEnv}`}>
          {publishingInfo.envLabel}
        </label>
      </div>
      {selected && (
        <div className="publish-option-description">
          Last updated:{" "}
          {publishingInfo.date ?
            moment(publishingInfo.date).format("dddd, MMMM D h:mma ZZ") :
            "never published"}
          <br />
          {publishingInfo.hasUnpublishedChanges && (
            <>
              <strong>You have unpublished changes.</strong>
              <br />
            </>
          )}
          <PublishForm
            onSubmit={handlePublish}
            disabled={!publishingInfo.hasUnpublishedChanges}
            website={website}
            option={publishingEnv}
          />
          <PublishStatusIndicator status={publishingInfo.status} />
        </div>
      )}
    </div>
  )
}

type Props = {
  visibility: boolean
  toggleVisibility: () => void
  website: Website
}
export default function PublishDrawer(props: Props): JSX.Element {
  const { visibility, toggleVisibility, website } = props
  const dispatch = useAppDispatch()
  const [selectedEnv, setSelectedEnv] = useState(PublishingEnv.Staging)

  const onPublishSuccess = async () => {
    toggleVisibility()
    await dispatch(requestAsync(websiteDetailRequest(website.name)))
  }

  const userEnvs = website.is_admin ?
    [PublishingEnv.Staging, PublishingEnv.Production] :
    [PublishingEnv.Staging]

  return (
    <Modal
      isOpen={visibility}
      toggle={toggleVisibility}
      modalClassName={`right ${website.publish_date ? "" : "wide"}`}
    >
      <ModalHeader toggle={toggleVisibility}>Publish your site</ModalHeader>
      <ModalBody>
        {userEnvs.map(publishingEnv => (
          <PublishingOption
            key={publishingEnv}
            website={website}
            publishingEnv={publishingEnv}
            selected={selectedEnv === publishingEnv}
            onPublishSuccess={onPublishSuccess}
            onSelect={setSelectedEnv}
          />
        ))}
        {website.content_warnings && !isEmpty(website.content_warnings) && (
          <div className="publish-warnings pt-2">
            <strong className="text-danger">
              This site has issues that could affect publishing output.
            </strong>
            <ul className="text-danger">
              {website.content_warnings.map((warning: string, idx: number) => (
                <li key={idx}>{warning}</li>
              ))}
            </ul>
          </div>
        )}
      </ModalBody>
    </Modal>
  )
}
