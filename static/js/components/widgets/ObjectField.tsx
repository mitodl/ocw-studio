import React, { useState, useCallback } from "react"

import SiteContentField from "../forms/SiteContentField"

import {
  ConfigField,
  ObjectConfigField,
  WebsiteContent
} from "../../types/websites"

interface Props {
  field: ObjectConfigField
  setFieldValue: (key: string, value: File | null) => void
  contentContext: WebsiteContent[] | null
}

/**
 * A widget which allows the sub-fields defined within an Object field
 * to be edited.
 **/
export default function ObjectField(props: Props): JSX.Element {
  const { field, setFieldValue, contentContext } = props

  const [collapsed, setCollapsed] = useState(field.collapsed ?? false)
  const toggleCollapse = useCallback(
    e => {
      e.preventDefault()
      setCollapsed(!collapsed)
    },
    [setCollapsed, collapsed]
  )

  return (
    <div className="object-widget">
      <div
        className="d-flex justify-content-between align-objects-center object-field-label"
        onClick={toggleCollapse}
      >
        <label htmlFor={field.name}>{field.label}</label>
        <i className="material-icons">
          {collapsed ? "expand_more" : "expand_less"}
        </i>
      </div>
      {collapsed ? null : (
        <div className="object-sub-fields">
          {field.fields?.map((field: ConfigField) => (
            <SiteContentField
              field={field}
              key={field.name}
              setFieldValue={setFieldValue}
              contentContext={contentContext}
            />
          ))}
        </div>
      )}
      {field.help && <span className="help-text">{field.help}</span>}
    </div>
  )
}
