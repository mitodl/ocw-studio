import React from "react"
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
  isSingletonCollectionItem
} from "../lib/site_content"
import { getResponseBodyError, isErrorResponse } from "../lib/util"

import { EditableConfigItem, Website, WebsiteContent } from "../types/websites"
import { ContentFormType, SiteFormValues } from "../types/forms"

interface Props {
  site: Website
  content?: WebsiteContent
  loadContent: boolean
  textId: string | null
  configItem: EditableConfigItem
  formType: ContentFormType
  hideModal?: () => void
  fetchWebsiteContentListing?: () => void
}

export default function SiteContentEditor(props: Props): JSX.Element | null {
  const {
    hideModal,
    configItem,
    textId,
    site,
    loadContent,
    formType,
    fetchWebsiteContentListing
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
    editWebsiteContentMutation(site, textId!, configItem.name, payload)
  )

  let isPending = false,
    content = null
  if (props.content) {
    content = props.content
  } else if (loadContent && textId) {
    const queryTuple = useRequest(
      websiteContentDetailRequest(site.name, textId)
    )
    isPending = queryTuple[0].isPending
    content = useSelector(getWebsiteContentDetailCursor)(textId)
  }

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
      values = { type: configItem.name, ...values }
    }
    const payload = contentFormValuesToPayload(values, configItem.fields)
    // If the content being created is for a singleton config item, use the config item "name" value as the text_id.
    if (
      formType === ContentFormType.Add &&
      isSingletonCollectionItem(configItem)
    ) {
      // @ts-ignore
      payload.text_id = configItem.name
    }

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

    if (fetchWebsiteContentListing) {
      // refresh to have the new item show up in the listing
      fetchWebsiteContentListing()
    }

    if (hideModal) {
      // turn off modal on success
      hideModal()
    }
  }

  return (
    <SiteContentForm
      onSubmit={onSubmitForm}
      configItem={configItem}
      content={content}
      formType={formType}
    />
  )
}
