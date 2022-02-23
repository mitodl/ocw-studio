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
import { ResourceType, ContentType } from "../../constants"
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
  id: TabIds
  contentType: ContentType
  resourcetype: string | null
  embeddable: boolean
  singleColumn: boolean
  sourceWebsiteName?: string
}

export enum TabIds {
  Documents = "documents",
  Images = "images",
  Videos = "videos",
  Pages = "pages",
  CourseCollections = "course_collections",
  ResourceCollections = "resource_collections"
}

const RESOURCE_PICKER_FULL_TABS: ResourceTabSettings[] = [
  {
    title:        "Documents",
    id:           TabIds.Documents,
    contentType:  ContentType.Resource,
    resourcetype: ResourceType.Document,
    embeddable:   true,
    singleColumn: true
  },
  {
    title:        "Videos",
    id:           TabIds.Videos,
    contentType:  ContentType.Resource,
    resourcetype: ResourceType.Video,
    embeddable:   true,
    singleColumn: false
  },
  {
    title:        "Images",
    id:           TabIds.Images,
    contentType:  ContentType.Resource,
    resourcetype: ResourceType.Image,
    embeddable:   true,
    singleColumn: false
  },
  {
    title:        "Pages",
    id:           TabIds.Pages,
    contentType:  ContentType.Page,
    resourcetype: null,
    embeddable:   false,
    singleColumn: true
  }
]
const RESOURCE_PICKER_DROPDOWN_TABS: ResourceTabSettings[] = [
  {
    title:             "Course Collections",
    id:                TabIds.CourseCollections,
    contentType:       ContentType.CourseCollections,
    resourcetype:      null,
    embeddable:        false,
    singleColumn:      true,
    sourceWebsiteName: "ocw-www"
  },
  {
    title:             "Resource Collections",
    id:                TabIds.ResourceCollections,
    contentType:       ContentType.ResourceCollections,
    resourcetype:      null,
    embeddable:        false,
    singleColumn:      true,
    sourceWebsiteName: "ocw-www"
  }
]
const RESOURCE_PICKER_ALL_TABS = [
  ...RESOURCE_PICKER_FULL_TABS,
  ...RESOURCE_PICKER_DROPDOWN_TABS
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

const isTabEnabled = (mode: ResourceDialogMode) => (tab: ResourceTabSettings) =>
  mode !== RESOURCE_EMBED || tab.embeddable

export default function ResourcePickerDialog(props: Props): JSX.Element {
  const { mode, isOpen, closeDialog, insertEmbed } = props

  const [activeTabId, setActiveTabId] = useState(TabIds.Images)
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

  const allTabs = RESOURCE_PICKER_ALL_TABS.filter(isTabEnabled(mode))
  const fullTabs = RESOURCE_PICKER_FULL_TABS.filter(isTabEnabled(mode))
  const dropdownTabs = RESOURCE_PICKER_DROPDOWN_TABS.filter(isTabEnabled(mode))
  const { acceptText, title } = modeText[mode]
  const activeTab = allTabs.find(t => t.id === activeTabId)
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
            {fullTabs.map(tab => (
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
            {dropdownTabs.length > 0 && (
              <Dropdown
                nav
                active={dropdownTabs.some(t => t.id === activeTabId)}
                isOpen={isDropdownOpen}
                toggle={() => setIsDropdownOpen(!isDropdownOpen)}
              >
                <DropdownToggle caret nav>
                  More
                </DropdownToggle>
                <DropdownMenu>
                  {dropdownTabs.map(tab => (
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
            {allTabs.map(tab => (
              <TabPane tabId={tab.id} key={tab.id}>
                {activeTabId === tab.id ? (
                  <ResourcePickerListing
                    resourcetype={tab.resourcetype}
                    contentType={tab.contentType}
                    filter={filter ?? null}
                    focusResource={setFocusedResource}
                    focusedResource={focusedResource}
                    singleColumn={tab.singleColumn}
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
