import React, { useState } from "react"
import { useSelector } from "react-redux"
import { Nav, NavItem, NavLink, TabContent, TabPane } from "reactstrap"
import { useRequest } from "redux-query-react"

import Card from "./Card"
import { useWebsite } from "../context/Website"

import { websiteContentDetailRequest } from "../query-configs/websites"

import { SingletonsConfigItem } from "../types/websites"
import { ContentFormType } from "../types/forms"

import { getWebsiteContentDetailCursor } from "../selectors/websites"
import SiteContentEditor from "./SiteContentEditor"
import { needsContentContext } from "../lib/site_content"

export default function SingletonsContentListing(props: {
  configItem: SingletonsConfigItem
}): JSX.Element | null {
  const { configItem } = props
  const website = useWebsite()

  const [activeTab, setActiveTab] = useState(0)
  const toggle = (tab: number) => {
    if (activeTab !== tab) setActiveTab(tab)
  }

  const activeFileConfigItem = configItem.files[activeTab]
  const content = useSelector(getWebsiteContentDetailCursor)(
    activeFileConfigItem.name
  )

  const [{ isPending }] = useRequest(
    content ?
      null :
      websiteContentDetailRequest(
        website.name,
        activeFileConfigItem.name,
        needsContentContext(activeFileConfigItem.fields)
      )
  )
  if (isPending) {
    return null
  }

  return (
    <div>
      <Nav tabs>
        {configItem.files.map((fileConfigItem, i) => (
          <NavItem key={i}>
            <NavLink
              className={activeTab === i ? "active" : ""}
              onClick={() => toggle(i)}
            >
              {fileConfigItem.label}
            </NavLink>
          </NavItem>
        ))}
      </Nav>
      <Card>
        <TabContent activeTab={activeTab}>
          {configItem.files.map((fileConfigItem, i) => (
            <TabPane key={i} tabId={i}>
              {isPending ? (
                "Loading..."
              ) : (
                <SiteContentEditor
                  content={content}
                  loadContent={false}
                  configItem={fileConfigItem}
                  textId={fileConfigItem.name}
                  formType={
                    content ? ContentFormType.Edit : ContentFormType.Add
                  }
                />
              )}
            </TabPane>
          ))}
        </TabContent>
      </Card>
    </div>
  )
}
