import React, { SyntheticEvent, useCallback, useState } from "react"
import { Nav, NavItem, NavLink, TabContent, TabPane } from "reactstrap"
import Switch from "react-switch"

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
  RESOURCE_EMBED,
  RESOURCE_LINK
} from "../../lib/ckeditor/plugins/constants"

interface Props {
  open: boolean
  setOpen: (open: boolean) => void
  insertEmbed: (id: string, variant: CKEResourceNodeType) => void
  attach: string
}

const RESOURCE_PICKER_TABS = [
  {
    title:    "Images",
    filetype: RESOURCE_TYPE_IMAGE
  },
  {
    title:    "Videos",
    filetype: RESOURCE_TYPE_VIDEO
  },
  {
    title:    "Documents",
    filetype: RESOURCE_TYPE_DOCUMENT
  }
]

export default function ResourcePickerDialog(props: Props): JSX.Element {
  const { open, setOpen, insertEmbed, attach } = props

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

  const [showFilterUI, setShowFilterUI] = useState(false)

  const setFilterUIChecked = useCallback(
    (
      checked: boolean,
      event:
        | MouseEvent
        | React.SyntheticEvent<MouseEvent | KeyboardEvent, Event>
    ) => {
      event.preventDefault()
      setShowFilterUI(checked)
    },
    [setShowFilterUI]
  )

  const [focusedResource, setFocusedResource] = useState<string | null>(null)

  const embedResource = useCallback(() => {
    if (focusedResource) {
      insertEmbed(focusedResource, RESOURCE_EMBED)
      setOpen(false)
    }
  }, [insertEmbed, focusedResource, setOpen])

  const linkResource = useCallback(() => {
    if (focusedResource) {
      insertEmbed(focusedResource, RESOURCE_LINK)
      setOpen(false)
    }
  }, [insertEmbed, focusedResource, setOpen])

  return (
    <Dialog
      open={open}
      toggleModal={() => setOpen(false)}
      wrapClassName="resource-picker-dialog"
      headerContent="Resources"
      onAccept={focusedResource ? embedResource : undefined}
      acceptText="Embed Resource"
      altOnAccept={focusedResource ? linkResource : undefined}
      altAcceptText="Link Resource"
      bodyContent={
        <>
          <Nav tabs>
            {RESOURCE_PICKER_TABS.map(tab => (
              <NavItem key={tab.filetype}>
                <NavLink
                  className={activeTab === tab.filetype ? "active" : ""}
                  onClick={() => {
                    setActiveTab(tab.filetype)
                  }}
                >
                  {tab.title}
                </NavLink>
              </NavItem>
            ))}
            <div className="show-all d-flex align-items-center">
              <span className="mx-2">Filter</span>
              <Switch
                uncheckedIcon={false}
                onChange={setFilterUIChecked}
                checked={showFilterUI}
              />
            </div>
          </Nav>
          {showFilterUI ? (
            <input
              placeholder="filter"
              type="text"
              onChange={onChangeFilter}
              value={filterInput}
              className="form-control filter-input my-2"
            />
          ) : null}
          <TabContent activeTab={activeTab}>
            {RESOURCE_PICKER_TABS.map(tab => (
              <TabPane tabId={tab.filetype} key={tab.filetype}>
                {activeTab === tab.filetype ? (
                  <ResourcePickerListing
                    filetype={tab.filetype}
                    filter={showFilterUI ? filter : null}
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
