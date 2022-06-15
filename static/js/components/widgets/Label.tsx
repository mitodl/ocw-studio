import React from "react"
import { filenameFromPath } from "../../lib/util"

export interface Props {
  name?: string
  value?: string | File | null
}

/**
 * A component for showing a read-only label; handleChange is not defined so this is readOnly
 */
const Label: React.FC<Props> = props => {
  const { value } = props
  return (
    <div className="form-group">
      {value && !(value instanceof File) ? (
        <div className="form-control">{filenameFromPath(value)}</div>
      ) : null}
    </div>
  )
}

export default Label
