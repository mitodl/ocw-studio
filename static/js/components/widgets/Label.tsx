import React from "react"
import { filenameFromPath } from "../../lib/util"

export interface Props {
  name?: string
  value?: string | File | null
}

/**
 * A component for showing a read-only label
 */
const Label: React.FC<Props> = props => {
  const { value } = props
  return (
    <div className="form-group">
      {value && !(value instanceof File) ? (
        <input
          className="form-control"
          placeholder={filenameFromPath(value)}
          type="text"
          readOnly
          style={{ cursor: "not-allowed" }}
        ></input>
      ) : null}
    </div>
  )
}

export default Label
