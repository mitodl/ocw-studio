import React, { useMemo } from "react"
import { useMutation, useRequest } from "redux-query-react"
import { useSelector } from "react-redux"
import { FormikHelpers } from "formik"

import SiteContentForm from "./forms/SiteContentForm"
import { useWebsite } from "../context/Website"

import {
  createWebsiteContentMutation,
  editWebsiteContentMutation,
  EditWebsiteContentPayload,
  NewWebsiteContentPayload,
  websiteContentDetailRequest
} from "../query-configs/websites"
import { getWebsiteContentDetailCursor } from "../selectors/websites"
import {
  addDefaultFields,
  contentFormValuesToPayload,
  isSingletonCollectionItem
} from "../lib/site_content"
import { getResponseBodyError, isErrorResponse } from "../lib/util"

import {
  ConfigField,
  EditableConfigItem,
  WebsiteContent
} from "../types/websites"
import { ContentFormType, SiteFormValues } from "../types/forms"

interface Props {
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
    loadContent,
    formType,
    fetchWebsiteContentListing
  } = props

  const fields: ConfigField[] = useMemo(() => addDefaultFields(configItem), [
    configItem
  ])
  const site = useWebsite()
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
  }

  const shouldLoadContent = !props.content && loadContent && textId

  const queryTuple = useRequest(
    shouldLoadContent ?
      websiteContentDetailRequest(site.name, textId as string) :
      null
  )
  const websiteContentDetailSelector = useSelector(
    getWebsiteContentDetailCursor
  )

  if (shouldLoadContent) {
    isPending = queryTuple[0].isPending
    content = websiteContentDetailSelector(textId as string)
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
    const payload = contentFormValuesToPayload(values, fields)
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
      fields={fields}
      configItem={configItem}
      content={content}
      formType={formType}
    />
  )
}
