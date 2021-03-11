import React from "react"
import { filenameFromPath } from "../../lib/util"

/**
 * A component for uploading files
 */

export interface Props {
  name?: string
  value?: string | File | null
  setFieldValue: (key: string, value: File | null) => void
}

export default function FileUploadField(props: Props): JSX.Element {
  const { name, value, setFieldValue } = props
  return (
    <div>
      <input
        type="file"
        name={name || "file"}
        onChange={event => {
          setFieldValue(
            "file",
            event.target.files ? event.target.files[0] : null
          )
        }}
        className="form-control"
      />
      {value && !(value instanceof File) ? (
        <div className="current-file">
          Current file: <a href={value}>{filenameFromPath(value)}</a>
        </div>
      ) : null}
    </div>
  )
}
