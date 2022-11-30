import React, { useState } from "react"
import { TabContent, TabPane, Nav, NavItem, NavLink } from "reactstrap"

import MarkdownEditor from "../components/widgets/MarkdownEditor"

import { TEST_MARKDOWN } from "../test_constants"

export default function MarkdownEditorTestPage(): JSX.Element {
  const [activeTab, setActiveTab] = useState("1")

  const toggle = (tab: string) => {
    if (activeTab !== tab) setActiveTab(tab)
  }

  return (
    <div>
      <Nav tabs>
        <NavItem>
          <NavLink
            className={activeTab === "1" ? "active" : ""}
            onClick={() => toggle("1")}
          >
            Minimal Editor
          </NavLink>
        </NavItem>
        <NavItem>
          <NavLink
            className={activeTab === "2" ? "active" : ""}
            onClick={() => toggle("2")}
          >
            Full Editor
          </NavLink>
        </NavItem>
      </Nav>
      <TabContent activeTab={activeTab}>
        <TabPane tabId="1">
          <MarkdownEditorTestWrapper minimal={true} />
        </TabPane>
        <TabPane tabId="2">
          <MarkdownEditorTestWrapper minimal={false} />
        </TabPane>
      </TabContent>
    </div>
  )
}

interface Props {
  minimal: boolean
}

function MarkdownEditorTestWrapper(props: Props) {
  const { minimal } = props

  const [data, setData] = useState(TEST_MARKDOWN)

  return (
    <div>
      <div className="w-75 m-auto">
        <h3>Editor</h3>
        <MarkdownEditor
          value={data}
          name="markdown"
          onChange={(event: any) => setData(event.target.value)}
          minimal={minimal}
          embed={[]}
          link={[]}
          allowedHtml={[]}
        />
      </div>
      <div className="w-75 m-auto">
        <h3>Output</h3>
        {data !== "" ? (
          <pre
            style={{
              border:     "2px solid red",
              maxWidth:   "100%",
              wordBreak:  "break-word",
              whiteSpace: "pre-wrap"
            }}
          >
            <code style={{ margin: "5px", display: "block" }}>{data}</code>
          </pre>
        ) : null}
      </div>
    </div>
  )
}
