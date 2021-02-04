import React, { useState } from "react"

import MarkdownEditor from "../components/MarkdownEditor"

export default function MarkdownEditorTestPage(): JSX.Element {
  const [data, setData] = useState("")

  return (
    <div>
      <div className="w-75 m-auto">
        <h3>Editor</h3>
        <MarkdownEditor initialData={data} onChange={setData} />
      </div>
      <div className="w-75 m-auto">
        <h3>Output</h3>
        {data !== "" ? (
          <pre
            style={{
              border:     "2px solid red",
              maxWidth:   "100%",
              wordBreak:  "break-word",
              whiteSpace: "pre-line"
            }}
          >
            <code style={{ margin: "5px", display: "block" }}>{data}</code>
          </pre>
        ) : null}
      </div>
    </div>
  )
}
