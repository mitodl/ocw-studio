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
    <div className="py-2">
      {value && !(value instanceof File) ? (
        <form className="current-file">
          <input value={filenameFromPath(value)} readOnly></input>
        </form>
      ) : null}
    </div>
  )
}

export default Label
