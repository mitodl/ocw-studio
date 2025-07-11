import React from "react"

export interface Props {
  name?: string
  value?: string | File
}

/**
 * A component for showing a read-only label
 */
const Label: React.FC<Props> = (props) => {
  const { value } = props
  return (
    <div className="form-group">
      {!(value instanceof File) ? (
        <input
          id={props.name}
          className="form-control"
          value={value ?? ""}
          type="text"
          readOnly
          style={{ cursor: "not-allowed" }}
        ></input>
      ) : null}
    </div>
  )
}

export default Label
