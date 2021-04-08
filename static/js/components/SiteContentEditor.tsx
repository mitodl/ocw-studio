import React from "react"
import { Modal, ModalBody, ModalHeader } from "reactstrap"
import { useMutation, useRequest } from "redux-query-react"
import { useSelector } from "react-redux"
import { FormikHelpers } from "formik"

import SiteContentForm from "./forms/SiteContentForm"

import {
  createWebsiteContentMutation,
  editWebsiteContentMutation,
  EditWebsiteContentPayload,
  NewWebsiteContentPayload,
  websiteContentDetailRequest
} from "../query-configs/websites"
import { getWebsiteContentDetailCursor } from "../selectors/websites"
import {
  contentFormValuesToPayload,
  splitFieldsIntoColumns
} from "../lib/site_content"
import { getResponseBodyError, isErrorResponse } from "../lib/util"

import { EditableConfigItem, Website } from "../types/websites"
import { ContentFormType, SiteFormValues } from "../types/forms"

interface Props {
  uuid: string | null
  visibility: boolean
  toggleVisibility: () => void
  site: Website
  configItem: EditableConfigItem
  formType: ContentFormType
  contentType: string
  websiteContentListingRequest: () => void
}

export default function SiteContentEditor(props: Props): JSX.Element | null {
  const {
    visibility,
    configItem,
    uuid,
    toggleVisibility,
    site,
    formType,
    contentType,
    websiteContentListingRequest
  } = props

  const [
    { isPending: addIsPending },
    addWebsiteContent
  ] = useMutation((payload: NewWebsiteContentPayload) =>
    createWebsiteContentMutation(site.name, payload)
  )
  const [
    { isPending: editIsPending },
    editWebsiteContent
  ] = useMutation((payload: EditWebsiteContentPayload | FormData) =>
    editWebsiteContentMutation(site, uuid!, configItem.name, payload)
  )

  const [{ isPending }] = useRequest(
    uuid ? websiteContentDetailRequest(site.name, uuid) : null
  )
  const websiteContentDetailCursor = useSelector(getWebsiteContentDetailCursor)
  const content = uuid ? websiteContentDetailCursor(uuid) : null

  if (isPending || (formType === ContentFormType.Edit && !content)) {
    return null
  }

  const onSubmitForm = async (
    values: SiteFormValues,
    { setErrors, setSubmitting, setStatus }: FormikHelpers<SiteFormValues>
  ) => {
    if (addIsPending || editIsPending) {
      return
    }
    if (formType === ContentFormType.Add) {
      values = { type: contentType, ...values }
    }
    const payload = contentFormValuesToPayload(values, configItem.fields)
    const response =
      formType === ContentFormType.Edit ?
        await editWebsiteContent(payload) :
        await addWebsiteContent(payload as NewWebsiteContentPayload)

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

    // refresh to have the new item show up in the listing
    websiteContentListingRequest()

    // turn off modal on success
    toggleVisibility()
  }

  const title = `${formType === ContentFormType.Edit ? "Edit" : "Add"} ${
    configItem.label
  }`
  const modalClassName = `right ${
    splitFieldsIntoColumns(configItem.fields ?? []).length > 1 ? "wide" : ""
  }`

  return (
    <div>
      <Modal
        isOpen={visibility}
        toggle={toggleVisibility}
        modalClassName={modalClassName}
      >
        <ModalHeader toggle={toggleVisibility}>{title}</ModalHeader>
        <ModalBody>
          <div className="m-3">
            <SiteContentForm
              onSubmit={onSubmitForm}
              configItem={configItem}
              content={content}
              formType={formType}
            />
          </div>
        </ModalBody>
      </Modal>
    </div>
  )
}
