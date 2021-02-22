import React, { useState } from "react"

import MarkdownEditor from "../components/MarkdownEditor"

export default function MarkdownEditorTestPage(): JSX.Element {
  const [data, setData] = useState("")

  return (
    <div>
      <div className="w-50">
        <h3>Editor</h3>
        <MarkdownEditor initialData={data} onChange={setData} />
      </div>
      <div className="w-50">
        <h3>Output</h3>
        {data !== "" ? (
          <pre style={{ border: "2px solid red" }}>
            <code style={{ margin: "5px", display: "block" }}>{data}</code>
          </pre>
        ) : null}
      </div>
    </div>
  )
}
