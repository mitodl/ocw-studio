import React, { useCallback } from "react"

import WebsiteCollectionForm from "./forms/WebsiteCollectionForm"

import { useMutation, useRequest } from "redux-query-react"
import { WebsiteCollectionFormFields } from "../types/forms"
import {
  WebsiteCollection,
  WebsiteCollectionModalState
} from "../types/website_collections"
import {
  createWebsiteCollectionMutation,
  editWebsiteCollectionMutation,
  websiteCollectionRequest
} from "../query-configs/website_collections"
import { useSelector } from "react-redux"
import { getWebsiteCollectionDetailCursor } from "../selectors/website_collections"

interface Props {
  hideModal: () => void
  modalState: WebsiteCollectionModalState
}

const initialFormValues = (
  collection: WebsiteCollection | null
): WebsiteCollectionFormFields =>
  collection ?
    { title: collection.title, description: collection.description } :
    { title: "", description: "" }

export default function WebsiteCollectionEditor(props: Props): JSX.Element {
  const { hideModal, modalState } = props

  const [
    ,
    editWebsiteCollection
  ] = useMutation((collection: WebsiteCollection) =>
    editWebsiteCollectionMutation(collection)
  )

  const [
    ,
    createWebsiteCollection
  ] = useMutation((collection: WebsiteCollectionFormFields) =>
    createWebsiteCollectionMutation(collection)
  )

  const websiteCollectionDetailCursor = useSelector(
    getWebsiteCollectionDetailCursor
  )

  const websiteCollection = modalState.editing() ?
    websiteCollectionDetailCursor(modalState.wrapped) :
    null

  const onSubmit = useCallback(
    async (collection: WebsiteCollectionFormFields) => {
      if (modalState.editing()) {
        await editWebsiteCollection({
          // this is just to get the .id prop from the website
          ...(websiteCollection as WebsiteCollection),
          ...collection
        })
      } else {
        await createWebsiteCollection(collection)
      }
      hideModal()
    },
    [
      editWebsiteCollection,
      modalState,
      createWebsiteCollection,
      websiteCollection,
      hideModal
    ]
  )

  const [{ isPending: fetchPending }] = useRequest(
    modalState.editing() ? websiteCollectionRequest(modalState.wrapped) : null
  )

  return fetchPending ? (
    <div>loading</div>
  ) : (
    <WebsiteCollectionForm
      initialValues={initialFormValues(websiteCollection)}
      onSubmit={onSubmit}
    />
  )
}
