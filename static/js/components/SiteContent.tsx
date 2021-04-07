import React from "react"
import {Modal, ModalBody, ModalHeader} from "reactstrap"
import {useMutation, useRequest} from "redux-query-react"
import {useSelector} from "react-redux"
import {FormikHelpers} from "formik"

import {
  createWebsiteContentMutation,
  editWebsiteContentMutation,
  EditWebsiteContentPayload,
  NewWebsiteContentPayload,
  websiteContentDetailRequest
} from "../query-configs/websites"
import {getWebsiteContentDetailCursor} from "../selectors/websites"
import SiteContentForm from "./forms/SiteContentForm"
import {contentFormValuesToPayload} from "../lib/site_content"
import {getResponseBodyError, isErrorResponse} from "../lib/util"

import {ConfigItem, Website} from "../types/websites"
import {ContentFormType} from "../types/forms";

type SiteFormValues = Record<string, string>

interface Props {
  uuid: string | null
  visibility: boolean
  toggleVisibility: () => void
  site: Website
  configItem: ConfigItem,
  formType: ContentFormType
}

export default function SiteContent(props: Props): JSX.Element | null {
  const { visibility, configItem, uuid, toggleVisibility, site, formType } = props

  const [
    { isPending: editIsPending },
    editWebsiteContent
  ] = useMutation((payload: EditWebsiteContentPayload | FormData) =>
    // @ts-ignore
    editWebsiteContentMutation(site, uuid, configItem.name, payload)
  )
  const [
    { isPending: addIsPending },
    addWebsiteContent
  ] = useMutation((payload: NewWebsiteContentPayload) =>
    createWebsiteContentMutation(site.name, payload)
  )

  // @ts-ignore
  const [{ isPending }] = useRequest(formType === ContentFormType.Edit ? websiteContentDetailRequest(site.name, uuid) : null)
  const content = useSelector(getWebsiteContentDetailCursor)(uuid)

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
    const payload = contentFormValuesToPayload(values, configItem.fields)
    const updateFunc = formType === ContentFormType.Edit ? editWebsiteContent : addWebsiteContent
    // @ts-ignore
    const response = await updateFunc(payload)
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
