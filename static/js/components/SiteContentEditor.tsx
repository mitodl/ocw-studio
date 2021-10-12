import React from "react"
import { useMutation, useRequest } from "redux-query-react"
import { useSelector, useStore } from "react-redux"
import { FormikHelpers } from "formik"
import { requestAsync } from "redux-query"

import SiteContentForm from "./forms/SiteContentForm"
import { useWebsite } from "../context/Website"

import {
  createWebsiteContentMutation,
  editWebsiteContentMutation,
  EditWebsiteContentPayload,
  NewWebsiteContentPayload,
  websiteContentDetailRequest,
  websiteDetailRequest
} from "../query-configs/websites"
import { getWebsiteContentDetailCursor } from "../selectors/websites"
import {
  contentFormValuesToPayload,
  isSingletonCollectionItem,
  needsContentContext
} from "../lib/site_content"
import { getResponseBodyError, isErrorResponse } from "../lib/util"

import {
  EditableConfigItem,
  WebsiteContentModalState,
  WebsiteContent
} from "../types/websites"
import { SiteFormValues } from "../types/forms"

interface Props {
  content?: WebsiteContent | null
  loadContent: boolean
  configItem: EditableConfigItem
  hideModal?: () => void
  fetchWebsiteContentListing?: () => void
  editorState: WebsiteContentModalState
}

export default function SiteContentEditor(props: Props): JSX.Element | null {
  const {
    hideModal,
    configItem,
    loadContent,
    fetchWebsiteContentListing,
    editorState
  } = props

  const site = useWebsite()
  const store = useStore()
  const refreshWebsite = () =>
    store.dispatch(requestAsync(websiteDetailRequest(site.name)))

  const [
    { isPending: addIsPending },
    addWebsiteContent
  ] = useMutation((payload: NewWebsiteContentPayload) =>
    createWebsiteContentMutation(site.name, payload)
  )

  const [
    { isPending: editIsPending },
    editWebsiteContent
  ] = useMutation((payload: EditWebsiteContentPayload | FormData, id: string) =>
    editWebsiteContentMutation({ name: site.name, textId: id }, payload)
  )

  let isPending = false,
    content = null
  if (props.content) {
    content = props.content
  }

  const shouldLoadContent = !props.content && loadContent

  const queryTuple = useRequest(
    shouldLoadContent && editorState.editing() ?
      websiteContentDetailRequest(
        { name: site.name, textId: editorState.wrapped },
        needsContentContext(configItem.fields)
      ) :
      null
  )
  const websiteContentDetailSelector = useSelector(
    getWebsiteContentDetailCursor
  )

  if (shouldLoadContent && editorState.editing()) {
    isPending = queryTuple[0].isPending

    content = websiteContentDetailSelector({
      name:   site.name,
      textId: editorState.wrapped
    })
  }

  if (isPending || (editorState.editing() && !content)) {
    return null
  }

  const onSubmitForm = async (
    values: SiteFormValues,
    { setErrors, setSubmitting, setStatus }: FormikHelpers<SiteFormValues>
  ) => {
    if (addIsPending || editIsPending) {
      return
    }
    if (editorState.adding()) {
      values = { type: configItem.name, ...values }
    }
    const payload = contentFormValuesToPayload(values, configItem.fields, site)

    // If the content being created is for a singleton config item,
    // use the config item "name" value as the text_id.
    if (editorState.adding() && isSingletonCollectionItem(configItem)) {
      payload["text_id"] = configItem.name
    }

    const response = editorState.editing() ?
      await editWebsiteContent(payload, editorState.wrapped) :
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

    // update the publish status
    refreshWebsite()

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
      editorState={editorState}
    />
  )
}
