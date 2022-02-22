import React, { SyntheticEvent, useCallback, useState } from "react"
import {
  Nav,
  NavItem,
  NavLink,
  TabContent,
  TabPane,
  Dropdown,
  DropdownItem,
  DropdownToggle,
  DropdownMenu
} from "reactstrap"

import Dialog from "../Dialog"
import {
  RESOURCE_TYPE_DOCUMENT,
  RESOURCE_TYPE_IMAGE,
  RESOURCE_TYPE_VIDEO,
  CONTENT_TYPE_RESOURCE,
  CONTENT_TYPE_PAGE,
  CONTENT_TYPE_COURSE_COLLECTION,
  CONTENT_TYPE_RESOURCE_COLLECTION
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
  contentType:
    | typeof CONTENT_TYPE_RESOURCE
    | typeof CONTENT_TYPE_PAGE
    | typeof CONTENT_TYPE_COURSE_COLLECTION
    | typeof CONTENT_TYPE_RESOURCE_COLLECTION
  resourcetype: string | null
  embeddable: boolean
  singleColumn: boolean
  sourceWebsiteName?: string
}

const RESOURCE_PICKER_TABS_MAIN: ResourceTabSettings[] = [
  {
    title:        "Documents",
    id:           RESOURCE_TYPE_DOCUMENT,
    contentType:  CONTENT_TYPE_RESOURCE,
    resourcetype: RESOURCE_TYPE_DOCUMENT,
    embeddable:   true,
    singleColumn: true
  },
  {
    title:        "Videos",
    id:           RESOURCE_TYPE_VIDEO,
    contentType:  CONTENT_TYPE_RESOURCE,
    resourcetype: RESOURCE_TYPE_VIDEO,
    embeddable:   true,
    singleColumn: false
  },
  {
    title:        "Images",
    id:           RESOURCE_TYPE_IMAGE,
    contentType:  CONTENT_TYPE_RESOURCE,
    resourcetype: RESOURCE_TYPE_IMAGE,
    embeddable:   true,
    singleColumn: false
  },
  {
    title:        "Pages",
    id:           CONTENT_TYPE_PAGE,
    contentType:  CONTENT_TYPE_PAGE,
    resourcetype: null,
    embeddable:   false,
    singleColumn: true
  }
]
const RESOURCE_PICKER_TABS_MORE: ResourceTabSettings[] = [
  {
    title:             "Course Collections",
    id:                CONTENT_TYPE_COURSE_COLLECTION,
    contentType:       CONTENT_TYPE_COURSE_COLLECTION,
    resourcetype:      null,
    embeddable:        false,
    singleColumn:      true,
    sourceWebsiteName: "ocw-www"
  },
  {
    title:             "Resource Collections",
    id:                CONTENT_TYPE_RESOURCE_COLLECTION,
    contentType:       CONTENT_TYPE_RESOURCE_COLLECTION,
    resourcetype:      null,
    embeddable:        false,
    singleColumn:      true,
    sourceWebsiteName: "ocw-www"
  }
]
const RESOURCE_PICKER_TABS = [
  ...RESOURCE_PICKER_TABS_MAIN,
  ...RESOURCE_PICKER_TABS_MORE
]

const modeText = {
  [RESOURCE_EMBED]: {
    title:      "Embed Resource",
    acceptText: "Embed resource"
  },
  [RESOURCE_LINK]: {
    title:      "Link to Content",
    acceptText: "Add link"
  }
}

export default function ResourcePickerDialog(props: Props): JSX.Element {
  const { mode, isOpen, closeDialog, insertEmbed } = props

  const tabsMain = RESOURCE_PICKER_TABS_MAIN.filter(
    tab => mode !== RESOURCE_EMBED || tab.embeddable
  )
  const tabsMore = RESOURCE_PICKER_TABS_MORE.filter(
    tab => mode !== RESOURCE_EMBED || tab.embeddable
  )
  const tabs = [...tabsMain, ...tabsMore]
  const [activeTabId, setActiveTabId] = useState(RESOURCE_TYPE_IMAGE)
  const [isDropdownOpen, setIsDropdownOpen] = useState(false)

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

  const { acceptText, title } = modeText[mode]
  const activeTab = RESOURCE_PICKER_TABS.find(t => t.id === activeTabId)
  const headerText = `${title}: ${activeTab?.title}`
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
            {tabsMain.map(tab => (
              <NavItem key={tab.id}>
                <NavLink
                  active={activeTabId === tab.id}
                  onClick={() => {
                    setActiveTabId(tab.id)
                  }}
                >
                  {tab.title}
                </NavLink>
              </NavItem>
            ))}
            {tabsMore.length > 0 && (
              <Dropdown
                nav
                active={RESOURCE_PICKER_TABS_MORE.some(
                  t => t.id === activeTabId
                )}
                isOpen={isDropdownOpen}
                toggle={() => setIsDropdownOpen(!isDropdownOpen)}
              >
                <DropdownToggle caret nav>
                  More
                </DropdownToggle>
                <DropdownMenu>
                  {tabsMore.map(tab => (
                    <DropdownItem
                      key={tab.id}
                      onClick={() => {
                        setActiveTabId(tab.id)
                      }}
                    >
                      {tab.title}
                    </DropdownItem>
                  ))}
                </DropdownMenu>
              </Dropdown>
            )}
          </Nav>
          <input
            placeholder="filter"
            type="text"
            onChange={onChangeFilter}
            value={filterInput}
            className="form-control filter-input my-2"
          />
          <TabContent activeTab={activeTabId}>
            {tabs.map(tab => (
              <TabPane tabId={tab.id} key={tab.id}>
                {activeTabId === tab.id ? (
                  <ResourcePickerListing
                    resourcetype={tab.resourcetype}
                    contentType={tab.contentType}
                    filter={filter ?? null}
                    focusResource={setFocusedResource}
                    focusedResource={focusedResource}
                    thumbnails={tab.singleColumn}
                    sourceWebsiteName={tab.sourceWebsiteName}
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
