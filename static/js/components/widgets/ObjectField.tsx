import React, { useState, useCallback } from "react"

import SiteContentField from "../forms/SiteContentField"
import { fieldIsVisible } from "../../lib/site_content"

import {
  ConfigField,
  ObjectConfigField,
  WebsiteContent
} from "../../types/websites"
import { SiteFormValues } from "../../types/forms"

interface Props {
  field: ObjectConfigField
  contentContext: WebsiteContent[] | null
  values: SiteFormValues
  onChange?: (e: React.ChangeEvent<any>) => void
}

/**
 * A widget which allows the sub-fields defined within an Object field
 * to be edited.
 **/
export default function ObjectField(props: Props): JSX.Element {
  const { field, contentContext, values, onChange } = props

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
        <label
          className="expandable-section-title font-weight-bold"
          htmlFor={field.name}
        >
          {field.label}
        </label>
        <i className="material-icons">
          {collapsed ? "expand_more" : "expand_less"}
        </i>
      </div>
      {collapsed ? null : (
        <div className="object-sub-fields">
          {field.fields
            .filter(innerField => fieldIsVisible(innerField, values))
            .map((innerField: ConfigField) => (
              <SiteContentField
                field={innerField}
                key={innerField.name}
                contentContext={contentContext}
                onChange={onChange}
              />
            ))}
        </div>
      )}
      {field.help && <span className="help-text">{field.help}</span>}
    </div>
  )
}
