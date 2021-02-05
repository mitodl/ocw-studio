import React, { useState } from "react"

import MarkdownEditor from "../components/MarkdownEditor"

const TEST_DATA = `## A heading

Amazing stuff! Paragraphs!

And another paragraph!

**bold** and even _italic_ text.

*   a
*   list
*   of
*   items
*   including
*   [links](https://reactjs.org/docs/hooks-faq.html#how-can-i-measure-a-dom-node)

also have some

> block quotes

good stuff.`

export default function MarkdownEditorTestPage() {
  const [markdown, setMarkdown] = useState(TEST_DATA)

  return (
    <div>
      <div className="w-50">
        <h3>Editor</h3>
        <MarkdownEditor initialData={markdown} onChange={setMarkdown} />
      </div>
      <div className="w-50">
        <h3>Output</h3>
    { markdown !== "" ?
        <pre style={{border: "2px solid red" }}>
          <code style={{margin: "5px", display: "block"}}>
            { markdown }
          </code>
        </pre>
        : null }
      </div>
    </div>
  )
}
