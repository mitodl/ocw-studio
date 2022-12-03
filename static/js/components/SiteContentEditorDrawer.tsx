import React, { useCallback, useEffect, useState } from "react"
import { useHistory, useLocation, useParams } from "react-router-dom"

import { useWebsite } from "../context/Website"
import { hasMainContentField } from "../lib/site_content"
import {
  WebsiteContentModalState,
  RepeatableConfigItem
} from "../types/websites"
import ConfirmDiscardChanges from "./util/ConfirmDiscardChanges"
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
    const initialLocation = history.location
    history.push({...history.location, pathname:
      siteContentListingUrl
        .param({
          name:        website.name,
          contentType: configItem.name
        })
        .toString()}
    )
    if (history.location !== initialLocation) {
      /**
       * Closing the modal is actually irrelevant in our current setup because
       * the component will no longer be visible when the route is updated.
       * But let's close it anyway.
       */
      setDrawerState(createModalState("closed"))
    }
  }, [website.name, configItem.name, search, history])

  const labelSingular = configItem.label_singular ?? singular(configItem.label)

  const modalTitle = `${
    drawerState.editing() ? "Edit" : "Add"
  } ${labelSingular}`

  const modalClassName = `right ${
    hasMainContentField(configItem.fields) ? "wide" : ""
  }`

  return (
    <>
      <ConfirmDiscardChanges when={dirty} />
      <BasicModal
        isVisible={drawerState.open()}
        hideModal={closeDrawer}
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
                dismiss={closeDrawer}
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
