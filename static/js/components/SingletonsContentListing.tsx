import React, { useEffect, useState } from "react"
import { Nav, NavItem, NavLink, TabContent, TabPane } from "reactstrap"
import { useLocation, useHistory } from "react-router-dom"

import Card from "./Card"
import { SingletonsConfigItem } from "../types/websites"
import SiteContentEditor from "./SiteContentEditor"
import { needsContentContext } from "../lib/site_content"
import { createModalState } from "../types/modal_state"
import { useWebsiteContent } from "../hooks/websites"
import ConfirmDiscardChanges from "./util/ConfirmDiscardChanges"

export default function SingletonsContentListing(props: {
  configItem: SingletonsConfigItem
}): JSX.Element | null {
  const { configItem } = props
  const { pathname } = useLocation()
  const hist = useHistory()
  window.hist = hist
  console.log("RENDER!")
  const [activeTab, setActiveTab] = useState(0)
  const toggle = (tab: number) => {
    if (activeTab !== tab) setActiveTab(tab)
  }
  const [dirty, setDirty] = useState(false)
  useEffect(() => {
    // make sure we clear state if we switch pages
    setDirty(false)
  }, [pathname])

  const activeFileConfigItem = configItem.files[activeTab]

  const [content, { isPending }] = useWebsiteContent(
    activeFileConfigItem.name,
    needsContentContext(activeFileConfigItem.fields)
  )
  if (isPending) {
    return null
  }

  return (
    <div>
      <ConfirmDiscardChanges when={dirty} />
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
                  content={activeTab === i ? content : null}
                  loadContent={false}
                  configItem={fileConfigItem}
                  editorState={
                    content ?
                      createModalState("editing", fileConfigItem.name) :
                      createModalState("adding")
                  }
                  setDirty={setDirty}
                />
              )}
            </TabPane>
          ))}
        </TabContent>
      </Card>
    </div>
  )
}
