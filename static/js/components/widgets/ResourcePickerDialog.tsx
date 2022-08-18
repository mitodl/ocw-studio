import React, {
  SyntheticEvent,
  useCallback,
  useMemo,
  useEffect,
  useState
} from "react"
import { Nav, NavItem, NavLink, TabContent, TabPane } from "reactstrap"

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
import { useWebsite } from "../../context/Website"
import _, { keyBy } from "lodash"

interface Props {
  mode: ResourceDialogMode
  isOpen: boolean
  closeDialog: () => void
  insertEmbed: (id: string, title: string, variant: CKEResourceNodeType) => void
  contentNames: string[]
}

interface TabSettings {
  title: string
  id: string
  contentType: string
  resourcetype: string | null
  embeddable: boolean
  singleColumn: boolean
}

const toTabSettings = (contentType: string, contentTitle: string) => {
  const newTabSettings: TabSettings = {
    title:        contentTitle,
    id:           contentType,
    contentType:  contentType,
    resourcetype: null,
    embeddable:   false,
    singleColumn: true
  }
  return newTabSettings
}

export enum TabIds {
  Other = "other",
  Documents = "documents",
  Images = "images",
  Videos = "videos",
  Pages = "pages",
  CourseCollections = "course-collection",
  ResourceCollections = "resource_collections",
  VideoGallery = "video_gallery",
  ResourceList = "resource-list"
}

const documentTab: TabSettings = {
  title:        "Documents",
  id:           TabIds.Documents,
  contentType:  ContentType.Resource,
  resourcetype: ResourceType.Document,
  embeddable:   false,
  singleColumn: true
}
const videoTab: TabSettings = {
  title:        "Videos",
  id:           TabIds.Videos,
  contentType:  ContentType.Resource,
  resourcetype: ResourceType.Video,
  embeddable:   true,
  singleColumn: false
}
const imageTab: TabSettings = {
  title:        "Images",
  id:           TabIds.Images,
  contentType:  ContentType.Resource,
  resourcetype: ResourceType.Image,
  embeddable:   true,
  singleColumn: false
}
const otherFilesTab: TabSettings = {
  title:        "Other",
  id:           TabIds.Other,
  contentType:  ContentType.Resource,
  resourcetype: ResourceType.Other,
  embeddable:   false,
  singleColumn: true
}

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
  const { mode, isOpen, closeDialog, insertEmbed, contentNames } = props
  const website = useWebsite()
  const definedCategories = useMemo(() => {
    const contentCollections =
      website.starter?.config?.collections.filter(
        entry => entry.category === "Content"
      ) ?? []
    return keyBy(contentCollections, collection => collection.name)
  }, [website.starter?.config?.collections])
  const tabs = useMemo(
    () =>
      contentNames
        .flatMap(name => {
          if (name && name === "resource") {
            return [documentTab, videoTab, imageTab, otherFilesTab]
          } else if (_.has(definedCategories, name)) {
            return [
              toTabSettings(
                definedCategories[name]["name"],
                definedCategories[name]["label"]
              )
            ]
          } else return []
        })
        .filter(tab => tab && (mode !== RESOURCE_EMBED || tab.embeddable)),
    [contentNames, definedCategories, mode]
  )

  const [activeTabId, setActiveTabId] = useState(tabs[0].id)

  useEffect(() => setActiveTabId(tabs[0].id), [tabs])

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

  return (
    <Dialog
      open={isOpen}
      onCancel={closeDialog}
      wrapClassName="resource-picker-dialog"
      headerContent={title}
      onAccept={focusedResource ? addResource : undefined}
      acceptText={focusedResource ? acceptText : undefined}
      bodyContent={
        <>
          <Nav tabs>
            {tabs.map(tab => (
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
                    singleColumn={tab.singleColumn}
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
