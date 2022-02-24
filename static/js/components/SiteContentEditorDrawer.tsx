import React, { useCallback, useEffect, useState } from "react"
import { useHistory, useLocation, useParams } from "react-router-dom"

import { useWebsite } from "../context/Website"
import { hasMainContentField } from "../lib/site_content"
import {
  WebsiteContentModalState,
  RepeatableConfigItem
} from "../types/websites"
import useConfirmation from "../hooks/confirmation"
import ConfirmationModal from "./ConfirmationModal"
import BasicModal from "./BasicModal"
import { singular } from "pluralize"
import { createModalState } from "../types/modal_state"
import SiteContentEditor from "./SiteContentEditor"
import { siteContentListingUrl } from "../lib/urls"

interface Props {
  configItem: RepeatableConfigItem
  fetchWebsiteContentListing: any
}

interface Params {
  uuid: string
}

export default function SiteContentEditorDrawer(
  props: Props
): JSX.Element | null {
  const { configItem, fetchWebsiteContentListing } = props

  const [drawerState, setDrawerState] = useState<WebsiteContentModalState>(
    createModalState("closed")
  )

  const website = useWebsite()

  const { uuid } = useParams<Params>()

  useEffect(() => {
    if (uuid !== undefined) {
      setDrawerState(createModalState("editing", uuid))
    } else {
      setDrawerState(createModalState("adding"))
    }
  }, [uuid])

  const [dirty, setDirty] = useState<boolean>(false)

  const history = useHistory()
  const { search } = useLocation()

  const closeDrawer = useCallback(() => {
    const queryParams = new URLSearchParams(search)
    history.push(
      siteContentListingUrl
        .param({
          name:        website.name,
          contentType: configItem.name
        })
        .query(queryParams)
        .toString()
    )
  }, [website.name, configItem.name, search, history])

  const {
    confirmationModalVisible,
    setConfirmationModalVisible,
    conditionalClose
  } = useConfirmation({
    dirty,
    setDirty,
    close: closeDrawer
  })

  const labelSingular = configItem.label_singular ?? singular(configItem.label)

  const modalTitle = `${
    drawerState.editing() ? "Edit" : "Add"
  } ${labelSingular}`

  const modalClassName = `right ${
    hasMainContentField(configItem.fields) ? "wide" : ""
  }`

  return (
    <>
      <ConfirmationModal
        dirty={dirty}
        confirmationModalVisible={confirmationModalVisible}
        setConfirmationModalVisible={setConfirmationModalVisible}
        dismiss={() => conditionalClose(true)}
      />
      <BasicModal
        isVisible={drawerState.open()}
        hideModal={() => conditionalClose(false)}
        title={modalTitle}
        className={modalClassName}
      >
        {() =>
          drawerState.open() ? (
            <div className="m-2">
              <SiteContentEditor
                loadContent={true}
                configItem={configItem}
                editorState={drawerState}
                dismiss={() => conditionalClose(true)}
                fetchWebsiteContentListing={fetchWebsiteContentListing}
                setDirty={setDirty}
              />
            </div>
          ) : null
        }
      </BasicModal>
    </>
  )
}
