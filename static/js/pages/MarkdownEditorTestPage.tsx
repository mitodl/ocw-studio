import React, { useState } from "react"

import MarkdownEditor from "../components/MarkdownEditor"

export default function MarkdownEditorTestPage() {
  const [markdown, setMarkdown] = useState("")

  return (
    <div>
      <MarkdownEditor initialData={markdown} onChange={setMarkdown} />
    </div>
  )
}
