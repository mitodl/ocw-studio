import React, { SyntheticEvent, useCallback, useState } from "react"
import { Nav, NavItem, NavLink, TabContent, TabPane } from "reactstrap"

import Dialog from "../Dialog"
import {
  RESOURCE_TYPE_DOCUMENT,
  RESOURCE_TYPE_IMAGE,
  RESOURCE_TYPE_VIDEO
} from "../../constants"
import ResourcePickerListing from "./ResourcePickerListing"
import { useDebouncedState } from "../../hooks/state"
import {
  CKEResourceNodeType,
  ResourceDialogState,
  RESOURCE_EMBED
} from "../../lib/ckeditor/plugins/constants"
import { WebsiteContent } from "../../types/websites"

interface Props {
  state: ResourceDialogState
  closeDialog: () => void
  insertEmbed: (id: string, title: string, variant: CKEResourceNodeType) => void
  attach: string
}

const RESOURCE_PICKER_TABS = [
  {
    title:        "Documents",
    resourcetype: RESOURCE_TYPE_DOCUMENT
  },
  {
    title:        "Videos",
    resourcetype: RESOURCE_TYPE_VIDEO
  },
  {
    title:        "Images",
    resourcetype: RESOURCE_TYPE_IMAGE
  }
]

export default function ResourcePickerDialog(props: Props): JSX.Element {
  const { state, closeDialog, insertEmbed, attach } = props

  const [activeTab, setActiveTab] = useState(RESOURCE_TYPE_IMAGE)

  // filterInput is to store user input and is updated synchronously
  // so that the UI stays responsive
  const [filterInput, setFilterInput] = useState("")
  // filter, by contrast, is set by the setFilterDebounced function
  // to cut down on extraneous requests.
  const [filter, setFilterDebounced] = useDebouncedState("", 300)

  const onChangeFilter = useCallback(
    (event: SyntheticEvent<HTMLInputElement>) => {
      const newFilter = event.currentTarget.value
      setFilterInput(newFilter)
      setFilterDebounced(newFilter)
    },
    [setFilterDebounced]
  )

  const [focusedResource, setFocusedResource] = useState<WebsiteContent | null>(
    null
  )

  const addResource = useCallback(() => {
    if (focusedResource && state !== "closed") {
      insertEmbed(
        focusedResource.text_id,
        focusedResource.title ?? focusedResource.text_id,
        state
      )
      closeDialog()
    }
  }, [insertEmbed, focusedResource, closeDialog, state])

  const acceptText =
    state === RESOURCE_EMBED ? "Embed resource" : "Link resource"

  return (
    <Dialog
      open={state !== "closed"}
      toggleModal={closeDialog}
      wrapClassName="resource-picker-dialog"
      headerContent="Resources"
      onAccept={focusedResource ? addResource : undefined}
      acceptText={focusedResource ? acceptText : undefined}
      bodyContent={
        <>
          <Nav tabs>
            {RESOURCE_PICKER_TABS.map(tab => (
              <NavItem key={tab.resourcetype}>
                <NavLink
                  className={activeTab === tab.resourcetype ? "active" : ""}
                  onClick={() => {
                    setActiveTab(tab.resourcetype)
                  }}
                >
                  {tab.title}
                </NavLink>
              </NavItem>
            ))}
          </Nav>
          <input
            placeholder="filter"
            type="text"
            onChange={onChangeFilter}
            value={filterInput}
            className="form-control filter-input my-2"
          />
          <TabContent activeTab={activeTab}>
            {RESOURCE_PICKER_TABS.map(tab => (
              <TabPane tabId={tab.resourcetype} key={tab.resourcetype}>
                {activeTab === tab.resourcetype ? (
                  <ResourcePickerListing
                    resourcetype={tab.resourcetype}
                    filter={filter ?? null}
                    focusResource={setFocusedResource}
                    focusedResource={focusedResource}
                    attach={attach}
                  />
                ) : null}
              </TabPane>
            ))}
          </TabContent>
        </>
      }
    />
  )
}
