import React from "react"
import { filenameFromPath } from "../../lib/util"

export interface Props {
  name?: string
  value?: string | File | null
  onChange: (event: any) => void
}

/**
 * A component for uploading files
 */
export default function FileUploadField(props: Props): JSX.Element {
  const { name, value, onChange } = props
  const fileInputName = name || "file"
  return (
    <div>
      <input
        type="file"
        name={fileInputName}
        onChange={(event) => {
          onChange({
            target: {
              name: event.target.name,
              value: event.target.files ? event.target.files[0] : null,
            },
          })
        }}
        className="form-control"
      />
      <input type="hidden" name="file_field_name" value={fileInputName} />
      {value && !(value instanceof File) ? (
        <div className="current-file">
          Current file: <a href={value}>{filenameFromPath(value)}</a>
        </div>
      ) : null}
    </div>
  )
}
