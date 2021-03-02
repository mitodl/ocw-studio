import React, { useState } from "react"

import MarkdownEditor from "../components/MarkdownEditor"

import { TEST_MARKDOWN } from "../test_constants"

export default function MarkdownEditorTestPage(): JSX.Element {
  const [data, setData] = useState(TEST_MARKDOWN)

  return (
    <div>
      <div className="w-75 m-auto">
        <h3>Editor</h3>
        <MarkdownEditor
          value={data}
          name="markdown"
          onChange={(event: any) => setData(event.target.value)}
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
