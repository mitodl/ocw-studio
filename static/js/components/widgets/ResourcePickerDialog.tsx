import React, { SyntheticEvent, useCallback, useState } from "react"
import { Nav, NavItem, NavLink, TabContent, TabPane } from "reactstrap"

import Dialog from "../Dialog"
import {
  RESOURCE_TYPE_DOCUMENT,
  RESOURCE_TYPE_IMAGE,
  RESOURCE_TYPE_VIDEO,
  CONTENT_TYPE_RESOURCE,
  CONTENT_TYPE_PAGE
} from "../../constants"
import ResourcePickerListing from "./ResourcePickerListing"
import { useDebouncedState } from "../../hooks/state"
import {
  CKEResourceNodeType,
  ResourceDialogMode,
  RESOURCE_EMBED,
  RESOURCE_LINK
} from "../../lib/ckeditor/plugins/constants"
import { WebsiteContent } from "../../types/websites"

interface Props {
  mode: ResourceDialogMode
  isOpen: boolean
  closeDialog: () => void
  insertEmbed: (id: string, title: string, variant: CKEResourceNodeType) => void
}

interface ResourceTabSettings {
  title: string
  id: string
  contentType: "resource" | "page"
  resourcetype: string | null
  embeddable: boolean
}
const RESOURCE_PICKER_TABS: ResourceTabSettings[] = [
  {
    title:        "Documents",
    id:           RESOURCE_TYPE_DOCUMENT,
    contentType:  CONTENT_TYPE_RESOURCE,
    resourcetype: RESOURCE_TYPE_DOCUMENT,
    embeddable:   true
  },
  {
    title:        "Videos",
    id:           RESOURCE_TYPE_VIDEO,
    contentType:  CONTENT_TYPE_RESOURCE,
    resourcetype: RESOURCE_TYPE_VIDEO,
    embeddable:   true
  },
  {
    title:        "Images",
    id:           RESOURCE_TYPE_IMAGE,
    contentType:  CONTENT_TYPE_RESOURCE,
    resourcetype: RESOURCE_TYPE_IMAGE,
    embeddable:   true
  },
  {
    title:        "Pages",
    id:           CONTENT_TYPE_PAGE,
    contentType:  CONTENT_TYPE_PAGE,
    resourcetype: null,
    embeddable:   false
  }
]

const modeText = {
  [RESOURCE_EMBED]: {
    headerText: "Resources",
    acceptText: "Embed resource"
  },
  [RESOURCE_LINK]: {
    headerText: "Resources & Pages",
    acceptText: "Add link"
  }
}

export default function ResourcePickerDialog(props: Props): JSX.Element {
  const { mode, isOpen, closeDialog, insertEmbed } = props

  const currentTabs = RESOURCE_PICKER_TABS.filter(
    tab => mode !== RESOURCE_EMBED || tab.embeddable
  )
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
    if (focusedResource && isOpen) {
      insertEmbed(
        focusedResource.text_id,
        focusedResource.title ?? focusedResource.text_id,
        mode
      )
      closeDialog()
    }
  }, [insertEmbed, focusedResource, closeDialog, isOpen, mode])

  const { acceptText, headerText } = modeText[mode]

  return (
    <Dialog
      open={isOpen}
      toggleModal={closeDialog}
      wrapClassName="resource-picker-dialog"
      headerContent={headerText}
      onAccept={focusedResource ? addResource : undefined}
      acceptText={focusedResource ? acceptText : undefined}
      bodyContent={
        <>
          <Nav tabs>
            {currentTabs.map(tab => (
              <NavItem key={tab.id}>
                <NavLink
                  className={activeTab === tab.id ? "active" : ""}
                  onClick={() => {
                    setActiveTab(tab.id)
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
            {currentTabs.map(tab => (
              <TabPane tabId={tab.id} key={tab.id}>
                {activeTab === tab.id ? (
                  <ResourcePickerListing
                    resourcetype={tab.resourcetype}
                    contentType={tab.contentType}
                    filter={filter ?? null}
                    focusResource={setFocusedResource}
                    focusedResource={focusedResource}
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
