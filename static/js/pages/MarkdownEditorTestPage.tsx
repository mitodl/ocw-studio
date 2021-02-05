import React, { useState } from "react"

import MarkdownEditor from "../components/MarkdownEditor"

const EDITOR_TAB = "editor"
const MARKDOWN_TAB = "markdown"

export default function MarkdownEditorTestPage() {
  const [markdown, setMarkdown] = useState("")

  const [currentTab, setTab] = useState(EDITOR_TAB)

  return (
    <div>
      <div className="w-50">
        <h3>Editor</h3>
        <MarkdownEditor initialData={markdown} onChange={setMarkdown} />
      </div>
      <div className="w-50">
        <h3>Output</h3>
        {markdown !== "" ? (
          <pre style={{ border: "2px solid red" }}>
            <code style={{ margin: "5px", display: "block" }}>{markdown}</code>
          </pre>
        ) : null}
      </div>
    </div>
  )
}
