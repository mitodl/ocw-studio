import React from "react"
import { Modal, ModalBody, ModalHeader } from "reactstrap"
import { useMutation, useRequest } from "redux-query-react"
import { useSelector } from "react-redux"
import { FormikHelpers } from "formik"

import {
  editWebsiteContentMutation,
  EditWebsiteContentPayload,
  websiteContentDetailRequest
} from "../query-configs/websites"
import { getWebsiteContentDetailCursor } from "../selectors/websites"
import SiteEditContentForm from "./forms/SiteEditContentForm"
import { contentFormValuesToPayload } from "../lib/site_content"
import { getResponseBodyError, isErrorResponse } from "../lib/util"

import { ConfigItem, Website } from "../types/websites"

type SiteFormValues = {
  [key: string]: string
}

interface Props {
  uuid: string
  visibility: boolean
  toggleVisibility: () => void
  site: Website
  configItem: ConfigItem
}

export default function SiteEditContent(props: Props): JSX.Element | null {
  const { visibility, configItem, uuid, toggleVisibility, site } = props

  const [
    { isPending: editIsPending },
    editWebsiteContent
  ] = useMutation((payload: EditWebsiteContentPayload | FormData) =>
    editWebsiteContentMutation(site, uuid, configItem.name, payload)
  )
  const [{ isPending }] = useRequest(
    websiteContentDetailRequest(site.name, uuid)
  )
  const content = useSelector(getWebsiteContentDetailCursor)(uuid)

  if (isPending || !content) {
    return null
  }

  const onSubmitForm = async (
    values: SiteFormValues,
    { setErrors, setSubmitting, setStatus }: FormikHelpers<SiteFormValues>
  ) => {
    if (editIsPending) {
      return
    }
    const payload = contentFormValuesToPayload(values, configItem.fields)
    const response = await editWebsiteContent(payload)
    if (!response) {
      return
    }
    // Display errors if any were returned
    if (isErrorResponse(response)) {
      const errors = getResponseBodyError(response)
      if (!errors) {
        return
      } else if (typeof errors === "string") {
        // Non-field error
        setStatus(errors)
      } else {
        setErrors(errors)
      }
      return
    }
    setSubmitting(false)

    // turn off modal on success
    toggleVisibility()
  }

  return (
    <div>
      <Modal
        isOpen={visibility}
        toggle={toggleVisibility}
        modalClassName="right"
      >
        <ModalHeader toggle={toggleVisibility}>
          Edit {configItem.name}
        </ModalHeader>
        <ModalBody>
          <div className="m-3">
            <SiteEditContentForm
              onSubmit={onSubmitForm}
              configItem={configItem}
              content={content}
            />
          </div>
        </ModalBody>
      </Modal>
    </div>
  )
}
